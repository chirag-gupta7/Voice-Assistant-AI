import { Capacitor } from '@capacitor/core';
import { Calendar as CapacitorCalendar } from '@capacitor-community/calendar';
import { meetingService } from './api';

const ensureDevicePermissions = async () => {
  const hasPerms = await CapacitorCalendar.hasReadWritePermission();
  if (!hasPerms?.granted) {
    await CapacitorCalendar.requestReadWritePermission();
  }
};

const createDeviceEvent = async (meeting) => {
  await ensureDevicePermissions();

  return CapacitorCalendar.createEvent({
    title: meeting.title,
    description: meeting.description || '',
    startDate: new Date(meeting.start_time).toISOString(),
    endDate: new Date(
      new Date(meeting.start_time).getTime() + (meeting.duration || 30) * 60000
    ).toISOString(),
    reminders: [5],
  });
};

const isNative = () => Capacitor.isNativePlatform?.() ?? false;

export const calendarManager = {
  async create(meeting, preference = 'local') {
    if (preference === 'device' && isNative()) {
      await createDeviceEvent(meeting);
      return { success: true, source: 'device' };
    }

    const response = await meetingService.createMeeting(meeting);
    return { success: true, source: 'local', data: response };
  },
};
