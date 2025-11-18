class VoiceService {
  constructor() {
    const speechWindow = typeof window !== 'undefined' ? window : {};
    const SpeechRecognition =
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition || null;

    if (SpeechRecognition) {
      this.recognition = new SpeechRecognition();
      this.recognition.lang = 'en-US';
      this.recognition.interimResults = false;
      this.recognition.maxAlternatives = 1;
    } else {
      this.recognition = null;
    }
  }

  isSupported() {
    return Boolean(this.recognition);
  }

  startListening() {
    return new Promise((resolve, reject) => {
      if (!this.recognition) {
        reject(new Error('Voice recognition is not supported in this browser.'));
        return;
      }

      this.recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        resolve(transcript);
      };

      this.recognition.onerror = (event) => {
        reject(new Error(event.error || 'Voice recognition error.'));
      };

      this.recognition.start();
    });
  }

  stopListening() {
    if (this.recognition) {
      this.recognition.stop();
    }
  }
}

export const voiceService = new VoiceService();
