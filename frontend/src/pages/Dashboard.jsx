import React, { useEffect, useState } from 'react';
import { Calendar, Plus } from 'lucide-react';
import VoiceInput from '../components/VoiceInput';
import { meetingService } from '../services/api';

const Dashboard = () => {
  const [meetings, setMeetings] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [showVoiceInput, setShowVoiceInput] = useState(false);

  useEffect(() => {
    loadMeetings();
  }, []);

  const loadMeetings = async () => {
    try {
      const data = await meetingService.getMeetings();
      setMeetings(data.meetings || []);
    } catch (error) {
      console.error('Failed to load meetings:', error);
    }
  };

  const handleVoiceTranscript = async (transcript) => {
    try {
      setProcessing(true);
      const result = await meetingService.processVoiceCommand(transcript);
      if (result.success) {
        await loadMeetings();
        setShowVoiceInput(false);
      }
    } catch (error) {
      console.error('Failed to process command:', error);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Your Meetings</h1>
        <button
          type="button"
          onClick={() => setShowVoiceInput((prev) => !prev)}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Plus className="h-5 w-5" />
          <span>{showVoiceInput ? 'Close Voice Scheduler' : 'Schedule Meeting'}</span>
        </button>
      </div>

      {showVoiceInput && (
        <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-center">Schedule with Voice</h2>
          <VoiceInput onTranscript={handleVoiceTranscript} onProcessing={setProcessing} />
          {processing && (
            <p className="text-center text-sm text-gray-500 mt-4">Processing your request…</p>
          )}
        </div>
      )}

      <div className="grid gap-4">
        {meetings.length === 0 ? (
          <div className="bg-white rounded-lg p-12 text-center border border-gray-200">
            <Calendar className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No meetings scheduled</h3>
            <p className="text-gray-500">Click "Schedule Meeting" to create your first meeting.</p>
          </div>
        ) : (
          meetings.map((meeting) => (
            <div
              key={meeting.id}
              className="bg-white rounded-lg p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{meeting.title}</h3>
                  <p className="text-gray-600 mt-1">{new Date(meeting.start_time).toLocaleString()}</p>
                  {meeting.description && (
                    <p className="text-gray-500 mt-2">{meeting.description}</p>
                  )}
                </div>
                <span className="px-3 py-1 bg-primary-100 text-primary-700 rounded-full text-sm">
                  {meeting.duration} min
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default Dashboard;
