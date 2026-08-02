package org.pymobile.app;

import android.app.Activity;
import android.util.Log;

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
    public static void vibrate(long milliseconds, int amplitude) {
        DeviceServices.vibrate(MainActivity.current(), milliseconds, amplitude);
    }

    /** Play a vibration pattern. */
    public static void vibratePattern(long[] pattern, int repeat) {
        DeviceServices.vibratePattern(MainActivity.current(), pattern, repeat);
    }

    /** Stop any ongoing vibration. */
    public static void cancelVibration() {
        DeviceServices.cancelVibration(MainActivity.current());
    }

    /** Post a notification on the given channel. */
    public static void notify(String title, String body, int id, boolean ongoing,
            String channelId, String channelName, String smallIcon) {
        Activity activity = MainActivity.current();
        Log.i("pymobile", "Native.notify() activity=" + (activity != null)
                + " title=" + title + " id=" + id);
        DeviceServices.notify(activity, title, body, id, ongoing,
                channelId, channelName, smallIcon);
    }

    /** Create a notification channel with the configured identity. */
    public static void ensureChannel(String channelId, String channelName, int importance) {
        Activity activity = MainActivity.current();
        Log.i("pymobile", "Native.ensureChannel() activity=" + (activity != null)
                + " channelId=" + channelId);
        DeviceServices.ensureChannel(activity, channelId, channelName, importance);
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

    /** The language the device is set to, as a BCP-47 tag such as "uk-UA". */
    public static String deviceLanguage() {
        return DeviceServices.deviceLanguage(MainActivity.current());
    }

    /** Open a URL in the system browser. */
    public static boolean openUrl(String url) {
        return DeviceServices.openUrl(MainActivity.current(), url);
    }
}
