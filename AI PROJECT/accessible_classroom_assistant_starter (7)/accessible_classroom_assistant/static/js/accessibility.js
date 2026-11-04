(() => {
  const root = document.documentElement;
  const body = document.body;
  let fontSize = 18;
  const status = document.getElementById("micStatus");
  const output = document.getElementById("captionOutput");
  let recognition = null;
  let finalTranscript = "";

  document.getElementById("increaseText")?.addEventListener("click", () => {
    fontSize = Math.min(28, fontSize + 2);
    root.style.setProperty("--base-font", `${fontSize}px`);
  });
  document.getElementById("decreaseText")?.addEventListener("click", () => {
    fontSize = Math.max(14, fontSize - 2);
    root.style.setProperty("--base-font", `${fontSize}px`);
  });
  document.getElementById("contrastToggle")?.addEventListener("click", (event) => {
    const enabled = body.classList.toggle("high-contrast");
    event.currentTarget.setAttribute("aria-pressed", String(enabled));
  });

  function getText(targetId) {
    const el = document.getElementById(targetId);
    return el ? ("value" in el ? el.value : el.innerText) : "";
  }
  function speak(text) {
    if (!("speechSynthesis" in window)) {
      alert("Text-to-speech is not supported in this browser.");
      return;
    }
    window.speechSynthesis.cancel();
    if (!text.trim()) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.92;
    window.speechSynthesis.speak(utterance);
  }
  document.querySelectorAll("[data-speak-target]").forEach(button => {
    button.addEventListener("click", () => speak(getText(button.dataset.speakTarget)));
  });
  document.getElementById("readPage")?.addEventListener("click", () => {
    const main = document.getElementById("main");
    speak(main ? main.innerText : document.body.innerText);
  });
  document.getElementById("stopSpeech")?.addEventListener("click", () => window.speechSynthesis?.cancel());
  document.getElementById("stopNotesSpeech")?.addEventListener("click", () => window.speechSynthesis?.cancel());
  document.getElementById("copyOcr")?.addEventListener("click", async () => {
    const text = getText("ocrText");
    try { await navigator.clipboard.writeText(text); alert("Text copied."); }
    catch { alert("Copy was blocked by the browser. Select the text and copy it manually."); }
  });

  const start = document.getElementById("startRecognition");
  const stop = document.getElementById("stopRecognition");
  const clear = document.getElementById("clearCaptions");
  const help = document.getElementById("speechHelp");

  if (start && output) {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      start.disabled = true;
      if (status) status.textContent = "Speech recognition unavailable";
      if (help) help.textContent = "This browser does not expose speech recognition. Try a supported browser or use the notes page to paste a transcript.";
    } else {
      recognition = new Recognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.onstart = () => { if (status) status.textContent = "Listening…"; };
      recognition.onerror = (event) => {
        if (status) status.textContent = `Recognition error: ${event.error}`;
      };
      recognition.onend = () => { if (status) status.textContent = "Captions stopped"; };
      recognition.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalTranscript += transcript + " ";
          else interim += transcript;
        }
        output.textContent = (finalTranscript + interim).trim() || "Listening for speech…";
      };
      start.addEventListener("click", () => {
        recognition.lang = document.getElementById("speechLanguage")?.value || "en-IN";
        try { recognition.start(); }
        catch { if (status) status.textContent = "Already listening. Stop and try again."; }
      });
      stop?.addEventListener("click", () => recognition.stop());
      clear?.addEventListener("click", () => {
        finalTranscript = "";
        output.textContent = "Your recognized speech will appear here.";
      });
    }
  }
})();
