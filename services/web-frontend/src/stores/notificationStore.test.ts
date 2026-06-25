import { describe, it, expect, beforeEach } from 'vitest';
import { useNotificationStore, type Notification } from './notificationStore';

describe('notificationStore', () => {
  const createNotification = (overrides: Partial<Notification> = {}): Notification => ({
    id: 'notif-1',
    type: 'info',
    title: 'Test Notification',
    message: 'This is a test notification',
    read: false,
    priority: 'normal',
    createdAt: new Date().toISOString(),
    ...overrides,
  });

  beforeEach(() => {
    useNotificationStore.setState({
      notifications: [],
      unreadCount: 0,
    });
  });

  describe('initial state', () => {
    it('should have empty notifications', () => {
      const state = useNotificationStore.getState();

      expect(state.notifications).toEqual([]);
      expect(state.unreadCount).toBe(0);
    });
  });

  describe('addNotification', () => {
    it('should add notification to the beginning of the list', () => {
      const { addNotification } = useNotificationStore.getState();
      const notif1 = createNotification({ id: 'notif-1' });
      const notif2 = createNotification({ id: 'notif-2' });

      addNotification(notif1);
      addNotification(notif2);

      const state = useNotificationStore.getState();
      expect(state.notifications).toHaveLength(2);
      expect(state.notifications[0].id).toBe('notif-2');
      expect(state.notifications[1].id).toBe('notif-1');
    });

    it('should update unread count when adding unread notification', () => {
      const { addNotification } = useNotificationStore.getState();

      addNotification(createNotification({ read: false }));

      expect(useNotificationStore.getState().unreadCount).toBe(1);
    });

    it('should not increment unread count when adding read notification', () => {
      const { addNotification } = useNotificationStore.getState();

      addNotification(createNotification({ read: true }));

      expect(useNotificationStore.getState().unreadCount).toBe(0);
    });

    it('should limit notifications to 100', () => {
      const { addNotification } = useNotificationStore.getState();

      // Add 105 notifications
      for (let i = 0; i < 105; i++) {
        addNotification(createNotification({ id: `notif-${i}` }));
      }

      expect(useNotificationStore.getState().notifications).toHaveLength(100);
    });
  });

  describe('markAsRead', () => {
    it('should mark notification as read', () => {
      const { addNotification, markAsRead } = useNotificationStore.getState();
      const notif = createNotification({ id: 'notif-1', read: false });
      addNotification(notif);

      markAsRead('notif-1');

      const state = useNotificationStore.getState();
      const updatedNotif = state.notifications.find((n) => n.id === 'notif-1');
      expect(updatedNotif?.read).toBe(true);
    });

    it('should update unread count when marking as read', () => {
      const { addNotification, markAsRead } = useNotificationStore.getState();
      addNotification(createNotification({ id: 'notif-1', read: false }));
      addNotification(createNotification({ id: 'notif-2', read: false }));

      expect(useNotificationStore.getState().unreadCount).toBe(2);

      markAsRead('notif-1');

      expect(useNotificationStore.getState().unreadCount).toBe(1);
    });

    it('should not affect other notifications', () => {
      const { addNotification, markAsRead } = useNotificationStore.getState();
      addNotification(createNotification({ id: 'notif-1', read: false }));
      addNotification(createNotification({ id: 'notif-2', read: false }));

      markAsRead('notif-1');

      const state = useNotificationStore.getState();
      const notif2 = state.notifications.find((n) => n.id === 'notif-2');
      expect(notif2?.read).toBe(false);
    });
  });

  describe('markAllAsRead', () => {
    it('should mark all notifications as read', () => {
      const { addNotification, markAllAsRead } = useNotificationStore.getState();
      addNotification(createNotification({ id: 'notif-1', read: false }));
      addNotification(createNotification({ id: 'notif-2', read: false }));
      addNotification(createNotification({ id: 'notif-3', read: true }));

      markAllAsRead();

      const state = useNotificationStore.getState();
      expect(state.unreadCount).toBe(0);
      expect(state.notifications.every((n) => n.read)).toBe(true);
    });
  });

  describe('removeNotification', () => {
    it('should remove notification by id', () => {
      const { addNotification, removeNotification } = useNotificationStore.getState();
      addNotification(createNotification({ id: 'notif-1' }));
      addNotification(createNotification({ id: 'notif-2' }));

      removeNotification('notif-1');

      const state = useNotificationStore.getState();
      expect(state.notifications).toHaveLength(1);
      expect(state.notifications[0].id).toBe('notif-2');
    });

    it('should update unread count when removing unread notification', () => {
      const { addNotification, removeNotification } = useNotificationStore.getState();
      addNotification(createNotification({ id: 'notif-1', read: false }));
      addNotification(createNotification({ id: 'notif-2', read: false }));

      removeNotification('notif-1');

      expect(useNotificationStore.getState().unreadCount).toBe(1);
    });

    it('should not affect unread count when removing read notification', () => {
      const { addNotification, removeNotification } = useNotificationStore.getState();
      addNotification(createNotification({ id: 'notif-1', read: true }));
      addNotification(createNotification({ id: 'notif-2', read: false }));

      removeNotification('notif-1');

      expect(useNotificationStore.getState().unreadCount).toBe(1);
    });
  });

  describe('clearAll', () => {
    it('should clear all notifications', () => {
      const { addNotification, clearAll } = useNotificationStore.getState();
      addNotification(createNotification({ id: 'notif-1' }));
      addNotification(createNotification({ id: 'notif-2' }));

      clearAll();

      const state = useNotificationStore.getState();
      expect(state.notifications).toEqual([]);
      expect(state.unreadCount).toBe(0);
    });
  });

  describe('setNotifications', () => {
    it('should set notifications array', () => {
      const { setNotifications } = useNotificationStore.getState();
      const notifications = [
        createNotification({ id: 'notif-1', read: false }),
        createNotification({ id: 'notif-2', read: true }),
      ];

      setNotifications(notifications);

      const state = useNotificationStore.getState();
      expect(state.notifications).toEqual(notifications);
    });

    it('should calculate correct unread count', () => {
      const { setNotifications } = useNotificationStore.getState();
      const notifications = [
        createNotification({ id: 'notif-1', read: false }),
        createNotification({ id: 'notif-2', read: true }),
        createNotification({ id: 'notif-3', read: false }),
      ];

      setNotifications(notifications);

      expect(useNotificationStore.getState().unreadCount).toBe(2);
    });
  });
});
