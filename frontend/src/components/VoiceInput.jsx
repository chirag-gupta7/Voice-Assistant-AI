import React, { useEffect, useState, useRef } from 'react';
import { Mic, MicOff, Square } from 'lucide-react';
import { voiceService } from '../services/voiceService';

const VoiceInput = ({ onTranscript, onProcessing }) => {
  const [isListening, setIsListening] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState(null);
  
  // State to track if this is the very first click
  const [isFirstInteraction, setIsFirstInteraction] = useState(true);

  // Ref to hold the audio element so we can stop it programmatically
  const audioRef = useRef(new Audio());

  useEffect(() => {
    if (!voiceService.isSupported()) {
      setError('Voice recognition is not supported in this browser. Please use Chrome.');
    }

    const audioEl = audioRef.current;

    // Cleanup audio on unmount
    return () => {
      if (audioEl) {
        audioEl.pause();
        audioEl.src = "";
      }
    };
  }, []);

  const playAudio = (base64Audio) => {
    return new Promise((resolve) => {
      if (!base64Audio) {
        resolve();
        return;
      }

      // Stop any currently playing audio
      audioRef.current.pause();
      
      const audioSrc = `data:audio/mp3;base64,${base64Audio}`;
      audioRef.current.src = audioSrc;
      
      setIsPlayingAudio(true);
      
      audioRef.current.onended = () => {
        setIsPlayingAudio(false);
        resolve();
      };
      
      audioRef.current.play().catch(e => {
        console.error("Audio play failed", e);
        setIsPlayingAudio(false);
        resolve();
      });
    });
  };

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsPlayingAudio(false);
    }
  };

  const handleInteraction = async () => {
    setError(null);

    // CASE 1: Currently Listening -> User wants to STOP manually
    if (isListening) {
      voiceService.stopListening();
      setIsListening(false);
      onProcessing(false);
      return;
    }

    // CASE 2: First Time Interaction -> Play Greeting THEN Listen
    if (isFirstInteraction) {
      setIsFirstInteraction(false); // Mark as done immediately
      onProcessing(true); // Show loading state while fetching greeting
      
      try {
        // Fetch greeting from backend
        const response = await fetch('/api/voice/greeting', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        const data = await response.json();

        if (data.success && data.audio_base64) {
          // Play greeting
          await playAudio(data.audio_base64);
          
          // After greeting ends, automatically start listening
          if (!audioRef.current.paused) return; // Edge case if user stopped it mid-way
          await startListeningInternal();
        } else {
          // Fallback if no audio
          await startListeningInternal();
        }
      } catch (err) {
        console.error("Greeting failed", err);
        // Fail gracefully to just listening
        await startListeningInternal();
      }
      return;
    }

    // CASE 3: Subsequent Interactions -> Interrupt Audio (if any) and Listen Immediately
    if (isPlayingAudio) {
      stopAudio();
    }
    await startListeningInternal();
  };

  const startListeningInternal = async () => {
    try {
      setIsListening(true);
      onProcessing(true);
      
      const result = await voiceService.startListening();
      
      setTranscript(result);
      onTranscript(result); // Pass to parent to handle sending to backend
    } catch (err) {
      setError(err.message);
    } finally {
      setIsListening(false);
      onProcessing(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <button
          type="button"
          onClick={handleInteraction}
          disabled={Boolean(error)}
          className={`relative p-8 rounded-full transition-all duration-300 ${
            isListening 
              ? 'bg-red-500 hover:bg-red-600 animate-pulse' 
              : isPlayingAudio 
                ? 'bg-green-500 hover:bg-green-600' // Visual cue for "AI Speaking"
                : 'bg-primary-600 hover:bg-primary-700'
          } ${error ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} shadow-lg hover:shadow-xl`}
        >
          {isListening ? (
             <Square className="h-12 w-12 text-white fill-current" />
          ) : isPlayingAudio ? (
             <MicOff className="h-12 w-12 text-white" /> // Icon indicating you can click to interrupt
          ) : (
             <Mic className="h-12 w-12 text-white" />
          )}

          {isListening && (
            <span className="absolute inset-0 rounded-full bg-red-400 animate-ping opacity-75" />
          )}
        </button>
      </div>

      <div className="text-center">
        {isListening && <p className="text-gray-600 animate-pulse">Listening...</p>}
        {isPlayingAudio && <p className="text-green-600 font-medium">AI is speaking... (Click to interrupt)</p>}
        {!isListening && !isPlayingAudio && !transcript && !error && (
          <p className="text-gray-500">
            {isFirstInteraction ? "Click to start Assistant" : "Click to speak again"}
          </p>
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
