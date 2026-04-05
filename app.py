import streamlit as st
import youtube_transcript_api
from youtube_transcript_api import YouTubeTranscriptApi
from groq import Groq
import re
import json
import time

# --- Configuration ---
GROQ_MODEL = "llama-3.3-70b-versatile"

# CSS for a premium look
st.set_page_config(page_title="YT Smart Speed", layout="wide")
st.markdown("""
<style>
    .main {
        background-color: #0f172a;
        color: #f1f5f9;
        font-family: 'Inter', sans-serif;
    }
    .stTextInput > div > div > input {
        background-color: #1e293b;
        color: #f1f5f9;
        border: 1px solid #334155;
    }
</style>
""", unsafe_allow_html=True)

# --- Functions ---

def extract_video_id(url):
    """Extract the video ID from a YouTube URL."""
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def fetch_transcript(video_id):
    """Fetch the transcript for a video using the ytt_api.fetch() method."""
    try:
        ytt_api = YouTubeTranscriptApi()
        
        # Try to fetch with a priority list of languages to avoid 'en' vs 'en-US' issues
        # The user's documentation shows .fetch(video_id, languages=['de', 'en'])
        try:
            fetched_transcript = ytt_api.fetch(video_id, languages=['en-US', 'en'])
        except Exception as e:
            st.warning(f"Default fetch failed, attempting to list and find any available transcript... Error: {e}")
            # Fallback: list all and take the first one available
            transcript_list = ytt_api.list(video_id)
            # Find any transcript (the user's docs show transcript_list.find_transcript(['de', 'en']))
            # We'll just take the first one from the list as a last resort
            if len(transcript_list) > 0:
                first_transcript = next(iter(transcript_list))
                fetched_transcript = first_transcript.fetch()
            else:
                raise Exception("No transcripts available for this video.")

        # Convert to raw data (list of dicts) as per user's documentation
        transcript = fetched_transcript.to_raw_data()
        
        # Convert start/duration to ms for the rest of the app logic
        blocks = []
        for entry in transcript:
            blocks.append({
                'start': entry['start'] * 1000,
                'end': (entry['start'] + entry['duration']) * 1000,
                'text': entry['text']
            })
        return blocks
    except Exception as e:
        st.error(f"Error fetching transcript: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Error fetching transcript: {str(e)}")
        return None

def analyze_with_groq(transcript_blocks, api_key):
    """Analyze the transcript with Groq in chunks."""
    client = Groq(api_key=api_key)
    
    # 1. Chunking into ~120 second segments
    chunks = []
    if not transcript_blocks: return []
    
    current_chunk = { 'id': 0, 'start': transcript_blocks[0]['start'], 'end': 0, 'text': "" }
    current_start = transcript_blocks[0]['start']
    chunk_dur = 120000 # 2 mins
    
    for block in transcript_blocks:
        if block['start'] >= current_start + chunk_dur:
            if current_chunk['text'].strip():
                chunks.append(current_chunk)
            current_chunk = { 'id': len(chunks), 'start': block['start'], 'end': block['end'], 'text': block['text'] }
            current_start = block['start']
        else:
            current_chunk['end'] = block['end']
            current_chunk['text'] += " " + block['text']
    if current_chunk['text'].strip(): chunks.append(current_chunk)

    # 2. API Batching
    all_results = []
    batch_size = 10
    
    system_prompt = """You are an AI that analyzes YouTube transcripts.
For each segment ID, determine:
1. Importance (1-10): 1=filler, 5=normal, 10=critical concept.
2. Notes: A 1-sentence summary IF importance >= 8. Else empty string.

Output ONLY a JSON object with a 'results' array.
Example: {"results": [{"id": 0, "importance": 4, "notes": ""}]}
"""

    progress_bar = st.progress(0)
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i+batch_size]
        batch_input = [{"id": b['id'], "text": b['text']} for b in batch]
        
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze these segments: {json.dumps(batch_input)}"}
                ],
                model=GROQ_MODEL,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            resp = json.loads(chat_completion.choices[0].message.content)
            batch_results = resp.get('results', [])
            
            # Map back to final segments with timestamps
            for b in batch:
                match = next((r for r in batch_results if r['id'] == b['id']), None)
                all_results.append({
                    'start': b['start'],
                    'end': b['end'],
                    'importance': match['importance'] if match else 5,
                    'notes': match['notes'] if match else ""
                })
        except Exception as e:
            st.warning(f"Batch analysis error: {e}")
            for b in batch:
                all_results.append({'start': b['start'], 'end': b['end'], 'importance': 5, 'notes': ""})

        progress_bar.progress((i + batch_size) / len(chunks) if i + batch_size < len(chunks) else 1.0)
    
    return all_results

# --- UI Layout ---

st.title("🚀 YouTube Smart Speed & Notes")
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    groq_key = st.text_input("Groq API Key", type="password")
    yt_url = st.text_input("YouTube URL")
    
    if st.button("🚀 Process Video", disabled=not (groq_key and yt_url)):
        video_id = extract_video_id(yt_url)
        if not video_id:
            st.error("Invalid YouTube URL")
        else:
            with st.spinner("Fetching transcript..."):
                transcript = fetch_transcript(video_id)
            
            if transcript:
                with st.spinner(f"Analyzing with {GROQ_MODEL}..."):
                    results = analyze_with_groq(transcript, groq_key)
                    if results:
                        # --- Dynamic Threshold Logic ---
                        avg_score = sum(r['importance'] for r in results) / len(results)
                        st.info(f"Average Importance Score: {avg_score:.2f}. Speeds adjusted dynamically.")
                        
                        for r in results:
                            # User requested: 1.5x for important, 1.75x and 2.0x for others
                            if r['importance'] >= avg_score:
                                r['speed'] = 1.5 # Significant content
                            elif r['importance'] >= avg_score * 0.7:
                                r['speed'] = 1.75 # Moderate content
                            else:
                                r['speed'] = 2.0 # Filler content
                        
                        st.session_state['analysis_results'] = results
                        st.session_state['video_id'] = video_id
                        st.success("Analysis complete!")

# --- Custom YouTube Player Component ---

if 'analysis_results' in st.session_state:
    results_json = json.dumps(st.session_state['analysis_results'])
    vid = st.session_state['video_id']
    
    st.markdown("### 📺 Player")
    
    # Custom HTML component that handles speed and pausing
    player_html = f"""
    <div id="player-container" style="position: relative; width: 100%; max-width: 800px; margin: auto;">
        <div id="yt-player"></div>
        <div id="notes-overlay" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); color:white; z-index:10; flex-direction:column; justify-content:center; align-items:center; text-align:center; padding: 20px; box-sizing: border-box;">
            <h2 style="color:#3b82f6;">Smart Notes</h2>
            <p id="note-text" style="font-size:1.2rem; margin: 20px 0;"></p>
            <button onclick="resumeVideo()" style="padding:10px 20px; background:#3b82f6; border:none; color:white; border-radius:5px; cursor:pointer;">Resume</button>
        </div>
        <div id="toast" style="position:absolute; top:20px; right:20px; background:rgba(0,0,0,0.7); color:white; padding:5px 15px; border-radius:20px; font-size:14px; opacity:0; transition:opacity 0.3s; z-index:5;"></div>
    </div>

    <script>
    var tag = document.createElement('script');
    tag.src = "https://www.youtube.com/iframe_api";
    var firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

    var player;
    var segments = {results_json};
    var currentSegmentIndex = -1;
    var lastProcessedNoteIndex = -1;

    function onYouTubeIframeAPIReady() {{
        player = new YT.Player('yt-player', {{
            height: '450',
            width: '100%',
            videoId: '{vid}',
            playerVars: {{
                'playsinline': 1,
                'rel': 0
            }},
            events: {{
                'onStateChange': onPlayerStateChange
            }}
        }});
    }}

    function onPlayerStateChange(event) {{
        if (event.data == YT.PlayerState.PLAYING) {{
            startMonitoring();
        }}
    }}

    var monitorInterval;
    function startMonitoring() {{
        if (monitorInterval) clearInterval(monitorInterval);
        monitorInterval = setInterval(() => {{
            if (!player || !player.getCurrentTime) return;
            
            var currentTimeMs = player.getCurrentTime() * 1000;
            
            // Check for notes
            for(let i=0; i < segments.length; i++) {{
                let s = segments[i];
                if (currentTimeMs > s.end && lastProcessedNoteIndex < i && s.notes && s.notes.trim()) {{
                     lastProcessedNoteIndex = i;
                     showNote(s.notes);
                     break;
                }}
                if (currentTimeMs > s.end && lastProcessedNoteIndex < i) {{
                    lastProcessedNoteIndex = i;
                }}
            }}

            // Find current segment for speed
            let currentSeg = segments.find(s => currentTimeMs >= s.start && currentTimeMs <= s.end);
            if (currentSeg) {{
                let index = segments.indexOf(currentSeg);
                if (index !== currentSegmentIndex) {{
                    currentSegmentIndex = index;
                    let targetSpeed = currentSeg.speed || 1.0;
                    
                    player.setPlaybackRate(targetSpeed);
                    showToast("Speed: " + targetSpeed + "x (Importance: " + currentSeg.importance + "/10)");
                }}
                
                // Enforce speed if reset
                let expectedSpeed = currentSeg.speed || 1.0;
                if (player.getPlaybackRate() !== expectedSpeed) {{
                    player.setPlaybackRate(expectedSpeed);
                }}
            }}
        }}, 500);
    }}

    function showNote(text) {{
        player.pauseVideo();
        document.getElementById('note-text').innerText = text;
        document.getElementById('notes-overlay').style.display = 'flex';
    }}

    function resumeVideo() {{
        document.getElementById('notes-overlay').style.display = 'none';
        player.playVideo();
    }}

    function showToast(msg) {{
        let t = document.getElementById('toast');
        t.innerText = msg;
        t.style.opacity = 1;
        setTimeout(() => {{ t.style.opacity = 0; }}, 2000);
    }}
    </script>
    """
    
    st.components.v1.html(player_html, height=500)
    
    st.markdown("---")
    st.markdown("### 📝 Analysis Review")
    st.table(st.session_state['analysis_results'])
