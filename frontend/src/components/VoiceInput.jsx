import React, { useEffect, useState } from 'react';
import { Mic, MicOff } from 'lucide-react';
import { voiceService } from '../services/voiceService';

const VoiceInput = ({ onTranscript, onProcessing }) => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!voiceService.isSupported()) {
      setError('Voice recognition is not supported in this browser. Please use Chrome.');
    }
  }, []);

  const startListening = async () => {
    try {
      setError(null);
      setIsListening(true);
      onProcessing(true);

      const result = await voiceService.startListening();
      setTranscript(result);
      onTranscript(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsListening(false);
      onProcessing(false);
    }
  };

  const stopListening = () => {
    voiceService.stopListening();
    setIsListening(false);
    onProcessing(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <button
          type="button"
          onClick={isListening ? stopListening : startListening}
          disabled={Boolean(error)}
          className={`relative p-8 rounded-full transition-all duration-300 ${
            isListening ? 'bg-red-500 hover:bg-red-600 animate-pulse' : 'bg-primary-600 hover:bg-primary-700'
          } ${error ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} shadow-lg hover:shadow-xl`}
        >
          {isListening ? (
            <MicOff className="h-12 w-12 text-white" />
          ) : (
            <Mic className="h-12 w-12 text-white" />
          )}

          {isListening && (
            <span className="absolute inset-0 rounded-full bg-red-400 animate-ping opacity-75" />
          )}
        </button>
      </div>

      <div className="text-center">
        {isListening && <p className="text-gray-600 animate-pulse">Listening... Speak now</p>}
        {!isListening && !transcript && !error && (
          <p className="text-gray-500">Click the microphone to start</p>
        )}
      </div>

      {transcript && (
        <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
          <p className="text-sm text-gray-500 mb-1">You said:</p>
          <p className="text-gray-900">{transcript}</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}
    </div>
  );
};

export default VoiceInput;
