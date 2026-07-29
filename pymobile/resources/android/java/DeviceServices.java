package org.pymobile.app;

import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.os.VibratorManager;
import android.util.Log;
import android.widget.Toast;

/**
 * Android platform features: vibration, notifications and runtime permissions.
 *
 * Every method tolerates a null activity, because Python may call in while the
 * activity is being recreated.
 */
final class DeviceServices {

    private static final String TAG = "pymobile";
    private static final String CHANNEL_ID = "pymobile.default";

    private DeviceServices() {
    }

    // -- vibration --------------------------------------------------------

    private static Vibrator vibrator(Context context) {
        if (context == null) {
            return null;
        }
        if (Build.VERSION.SDK_INT >= 31) {
            VibratorManager manager =
                    (VibratorManager) context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE);
            return manager == null ? null : manager.getDefaultVibrator();
        }
        return (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
    }

    /**
     * Vibrate once.
     *
     * Implemented as a one-entry waveform rather than createOneShot: on several
     * devices (Pixel among them) createOneShot with DEFAULT_AMPLITUDE is
     * silently ignored, while waveforms are honoured. Very short pulses are
     * also stretched, because anything under ~50 ms is imperceptible on most
     * hardware and looks like a bug to the user.
     */
    static void vibrate(Context context, long milliseconds) {
        long duration = Math.max(milliseconds, MIN_PERCEPTIBLE_MS);
        vibratePattern(context, new long[]{0, duration}, -1);
    }

    /** Below this, a pulse is not reliably felt on typical hardware. */
    private static final long MIN_PERCEPTIBLE_MS = 50;

    static void vibratePattern(Context context, long[] pattern, int repeat) {
        Vibrator vibrator = vibrator(context);
        if (vibrator == null || pattern == null || pattern.length == 0) {
            return;
        }
        if (Build.VERSION.SDK_INT >= 26) {
            // Explicit amplitudes: some devices treat the default as "off".
            int[] amplitudes = new int[pattern.length];
            for (int i = 0; i < pattern.length; i++) {
                amplitudes[i] = (i % 2 == 0) ? 0 : 255;
            }
            try {
                vibrator.vibrate(VibrationEffect.createWaveform(pattern, amplitudes, repeat));
            } catch (IllegalArgumentException error) {
                // Devices without amplitude control reject the array form.
                vibrator.vibrate(VibrationEffect.createWaveform(pattern, repeat));
            }
        } else {
            vibrator.vibrate(pattern, repeat);
        }
    }

    static void cancelVibration(Context context) {
        Vibrator vibrator = vibrator(context);
        if (vibrator != null) {
            vibrator.cancel();
        }
    }

    // -- notifications ----------------------------------------------------

    private static NotificationManager notificationManager(Context context) {
        if (context == null) {
            return null;
        }
        return (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
    }

    static void notify(Context context, String title, String body, int id, boolean ongoing) {
        NotificationManager manager = notificationManager(context);
        if (manager == null) {
            return;
        }
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "General", NotificationManager.IMPORTANCE_DEFAULT);
            manager.createNotificationChannel(channel);
        }

        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= 26) {
            builder = new Notification.Builder(context, CHANNEL_ID);
        } else {
            builder = new Notification.Builder(context);
        }
        builder.setContentTitle(title)
                .setContentText(body)
                .setOngoing(ongoing)
                .setAutoCancel(!ongoing)
                .setSmallIcon(iconResource(context));
        try {
            manager.notify(id, builder.build());
        } catch (SecurityException error) {
            Log.w(TAG, "POST_NOTIFICATIONS not granted", error);
        }
    }

    static void cancelNotification(Context context, int id) {
        NotificationManager manager = notificationManager(context);
        if (manager != null) {
            manager.cancel(id);
        }
    }

    /** Resolve the launcher icon, falling back to a platform drawable. */
    private static int iconResource(Context context) {
        int found = context.getResources().getIdentifier(
                "icon", "mipmap", context.getPackageName());
        return found != 0 ? found : android.R.drawable.ic_dialog_info;
    }

    // -- permissions ------------------------------------------------------

    static boolean hasPermission(Context context, String permission) {
        if (context == null) {
            return false;
        }
        if (Build.VERSION.SDK_INT < 23) {
            return true;
        }
        return context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
    }

    /**
     * Show the system dialog and wait for the user's answer.
     *
     * requestPermissions() is asynchronous. Returning immediately meant Python
     * re-checked the permission before the user had tapped anything and always
     * saw "denied", so this blocks the calling (Python) thread until
     * MainActivity reports the result.
     */
    static boolean requestPermission(Activity activity, String permission) {
        if (activity == null) {
            return false;
        }
        if (Build.VERSION.SDK_INT < 23 || hasPermission(activity, permission)) {
            return true;
        }
        return MainActivity.requestPermissionBlocking(activity, permission);
    }

    // -- misc -------------------------------------------------------------

    static void toast(Activity activity, String message, boolean longer) {
        if (activity == null) {
            return;
        }
        Toast.makeText(activity, message,
                longer ? Toast.LENGTH_LONG : Toast.LENGTH_SHORT).show();
    }

    /**
     * The language the device is set to, as a BCP-47 tag such as "uk-UA".
     *
     * Read from the configuration rather than Locale.getDefault() so that a
     * per-app language override (Android 13's per-app languages) is honoured.
     * Returns an empty string when it cannot be determined, which tells the
     * Python side to fall back to its own detection.
     */
    static String deviceLanguage(Context context) {
        java.util.Locale locale = null;
        if (context != null) {
            android.content.res.Configuration config =
                    context.getResources().getConfiguration();
            if (Build.VERSION.SDK_INT >= 24) {
                android.os.LocaleList locales = config.getLocales();
                if (!locales.isEmpty()) {
                    locale = locales.get(0);
                }
            } else {
                locale = config.locale;
            }
        }
        if (locale == null) {
            locale = java.util.Locale.getDefault();
        }
        if (locale == null) {
            return "";
        }
        String language = locale.getLanguage();
        if (language == null || language.isEmpty()) {
            return "";
        }
        String country = locale.getCountry();
        return (country == null || country.isEmpty()) ? language : language + "-" + country;
    }
}
