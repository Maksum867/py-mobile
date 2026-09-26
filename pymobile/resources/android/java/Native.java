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

    /**
     * Payload Python sends through render() to wake its own event loop.
     * The prebuilt libpymobile.so has no dedicated "post event" call, so a
     * background Python thread reaches the C event queue through here.
     */
    static final String WAKE = "{\"__wake__\":true}";

    /** Render a serialised widget tree (JSON). */
    public static void render(String json) {
        if (WAKE.equals(json)) {
            // Runs on the calling (background Python) thread: only queues an
            // event, the interpreter's loop thread picks it up.
            dispatchEvent("", "__wake__", "");
            return;
        }
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

    /**
     * Vibrate once at the default strength.
     *
     * Kept for the prebuilt libpymobile.so, which was compiled against the
     * older one-argument signature. Without it the prebuilt bridge logs
     * "method not found: vibrate(J)V" and the phone stays still.
     */
    public static void vibrate(long milliseconds) {
        vibrate(milliseconds, -1);
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

    /**
     * Post a notification on the default channel.
     *
     * Kept for the prebuilt libpymobile.so (older four-argument signature);
     * see {@link #vibrate(long)}.
     */
    public static void notify(String title, String body, int id, boolean ongoing) {
        notify(title, body, id, ongoing, null, null, null);
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

    /** Ask the launcher Activity to finish (the root back button). */
    public static void finishApp() {
        MainActivity.finishApp();
    }
}
