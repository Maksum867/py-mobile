package org.pymobile.app;

/**
 * The single Java entry point the native layer talks to.
 *
 * Keeping every JNI-visible signature in one small class means the C code has
 * exactly one class to look up, and the rest of the Java side stays free to
 * change without touching the bridge.
 */
public final class Native {

    private Native() {
    }

    /** Python → Java: called from the interpreter thread. */
    public static native void dispatchEvent(String widgetId, String type, String value);

    /** Wake the interpreter's event loop so it can exit. */
    public static native void stopEventLoop();

    // -- calls made by the native module ---------------------------------

    /** Render a serialised widget tree (JSON). */
    public static void render(String json) {
        MainActivity activity = MainActivity.current();
        if (activity != null) {
            activity.renderTree(json);
        }
    }

    /** Show a toast. */
    public static void toast(String message, boolean longer) {
        MainActivity activity = MainActivity.current();
        if (activity != null) {
            activity.showToast(message, longer);
        }
    }

    /** Vibrate once. */
    public static void vibrate(long milliseconds) {
        DeviceServices.vibrate(MainActivity.current(), milliseconds);
    }

    /** Play a vibration pattern. */
    public static void vibratePattern(long[] pattern, int repeat) {
        DeviceServices.vibratePattern(MainActivity.current(), pattern, repeat);
    }

    /** Stop any ongoing vibration. */
    public static void cancelVibration() {
        DeviceServices.cancelVibration(MainActivity.current());
    }

    /** Post a notification. */
    public static void notify(String title, String body, int id, boolean ongoing) {
        DeviceServices.notify(MainActivity.current(), title, body, id, ongoing);
    }

    /** Cancel a notification. */
    public static void cancelNotification(int id) {
        DeviceServices.cancelNotification(MainActivity.current(), id);
    }

    /** Whether a runtime permission is granted. */
    public static boolean hasPermission(String permission) {
        return DeviceServices.hasPermission(MainActivity.current(), permission);
    }

    /** Ask the user for a runtime permission, waiting for the answer. */
    public static boolean requestPermission(String permission) {
        return DeviceServices.requestPermission(MainActivity.current(), permission);
    }
}
