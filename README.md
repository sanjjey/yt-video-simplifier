# 🚀 YouTube Smart Speed & Notes (Streamlit)

Enhance your learning experience by automatically adjusting YouTube playback speed based on the importance of the content and generating study notes on the fly.

## ✨ Features

- **Smart Transcript Extraction**: Automatically fetches manual and auto-generated captions for any YouTube video.
- **AI-Powered Importance Analysis**: Uses **Groq (Llama 3.3 70B)** to analyze the density and importance of every 2-minute segment.
- **Dynamic Speed Scaling**:
    - Calculates the **Average Importance Score** of the entire video.
    - Adjusts playback speed relatively:
        - **1.5x**: Important concepts (at or above average).
        - **1.75x**: Moderate content.
        - **2.0x**: Filler/Intro/Outro content.
- **Automatic Note Taking**: Automatically pauses the video when a critical concept finishes and displays an AI-generated summary overlay.
- **Interactive Player**: A custom YouTube IFrame API implementation that gives you real-time feedback with speed "toast" notifications.

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.8 or higher.
- A [Groq API Key](https://console.groq.com/).

### Installation

1. Navigate to the `streamlit_app` directory:
   ```powershell
   cd streamlit_app
   ```

2. Install the required dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

### Running the App

Start the Streamlit server:
```powershell
streamlit run app.py
```

## 📖 How to Use

1. **API Key**: Enter your Groq API Key in the sidebar/input field.
2. **Video URL**: Paste the URL of the YouTube video you want to watch (e.g., a technical lecture, deep-dive, or tutorial).
3. **Analyze**: Click the **Process Video** button.
4. **Watch**: The player will load. As you watch:
    - The speed will shift automatically between 1.5x and 2.0x.
    - When a "Smart Note" is ready, the video will pause. Read/Copy your note and click **Resume** to continue.

## 🧰 Technologies Used

- **Frontend**: [Streamlit](https://streamlit.io/)
- **AI Engine**: [Groq API](https://groq.com/) (Model: `llama-3.3-70b-versatile`)
- **Data**: [YouTube Transcript API](https://github.com/jdepoix/youtube-transcript-api)
- **Player Control**: YouTube IFrame API (Custom Javascript Implementation)
