# Accessible Text-to-Speech & Speech-to-Text Classroom Assistant

- Role-based login and portals for **Lecturer** and **Student**.
- Browser-based speech-to-text captions (requires a supported browser; availability varies).
- Text-to-speech using the browser's speech synthesis.
- Image-to-text OCR through Tesseract.
- Offline extractive summaries and keyword extraction.
- SQLite storage for lecture notes with lecturer sharing permissions.
- Keyboard-friendly interface, adjustable text size, and high-contrast mode.

## Demo Login Accounts
You can use the **1-Click Demo Buttons** on the login page, or log in with:
- **Lecturer:** Username `lecturer` | Password `lecturer123` (Prof. Sharma)
- **Student:** Username `student` | Password `student123` (Rahul Kumar)
- You can also register new accounts at `/register`.

## 1. Requirements
- Python 3.10 or newer recommended.
- Google Chrome or another browser supporting the Web Speech API for speech recognition.
- For OCR: install the **Tesseract OCR application** separately, then install the Python packages listed in `requirements.txt`.
- Internet is not required for the basic Flask application after dependencies are installed. Browser speech recognition may rely on an online service depending on the browser.

## 2. Run on Windows
Open Command Prompt or PowerShell in this project folder:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## 3. OCR setup
Install the Tesseract OCR application for your operating system. If Python cannot locate it on Windows, configure the path in `app.py` before calling `pytesseract.image_to_string`, for example:

```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

The exact path may differ on your computer.

## 4. Features and limitations
- Speech captions use browser recognition. It is not a guaranteed offline or word-perfect transcription engine.
- Text-to-speech uses voices available in the user's browser/device.
- OCR works best with clear, straight, well-lit printed text.
- Summaries use a simple extractive algorithm, not a trained generative AI model.
- The ESP32, display, and vibration motor from the synopsis are **not yet integrated**. They can be added as a later hardware phase.
- This is an educational prototype, not a certified accessibility or medical device. Test with real users and provide manual fallbacks.

## 5. Project structure
```text
accessible_classroom_assistant/
├── app.py
├── requirements.txt
├── README.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── ocr.html
│   ├── notes.html
│   └── saved_note.html
├── static/
│   ├── css/style.css
│   └── js/accessibility.js
└── uploads/
```
