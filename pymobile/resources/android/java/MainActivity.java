package org.pymobile.app;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * The launcher activity.
 *
 * Owns the view container and runs the Python interpreter on a background
 * thread. Python pushes widget trees in through {@link #renderTree}; the views
 * are always built and swapped on the UI thread.
 */
public class MainActivity extends Activity {

    private static final String TAG = "pymobile";
    private static MainActivity instance;

    private FrameLayout container;
    private ViewBuilder builder;
    private final Handler ui = new Handler(Looper.getMainLooper());

    /** True once the first widget tree has been handed to the UI thread. */
    private volatile boolean rendered = false;

    /** Set while a permission dialog is open; counted down by the callback. */
    private static volatile CountDownLatch permissionLatch;
    private static volatile boolean permissionGranted;
    private static final int PERMISSION_REQUEST = 1000;

    /**
     * Released once the activity reaches the resumed state.
     *
     * Python starts from onCreate and may ask for a permission immediately.
     * requestPermissions() issued before the window is ready is dropped by the
     * system without ever showing a dialog, which looks like an instant denial.
     */
    private static final CountDownLatch resumedLatch = new CountDownLatch(1);

    /** The running activity, or null while it is being recreated. */
    static MainActivity current() {
        return instance;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        instance = this;

        container = new FrameLayout(this);
        container.setBackgroundColor(Color.WHITE);
        setContentView(container);
        builder = new ViewBuilder(this);

        showPlaceholder("Starting Python…");
        // Tell PythonRuntime to report the long first-launch extraction.
        PythonRuntime.onStatus = new Runnable() {
            @Override
            public void run() {
                postPlaceholder("First launch: extracting the Python runtime…");
            }
        };

        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    // The entry point comes from assets/pymobile.properties
                    // (defaulting to main.py), so a project that configures a
                    // different `entrypoint` actually runs that file.
                    int status = PythonRuntime.run(getApplicationContext());
                    Log.i(TAG, "python exited with " + status);
                    if (!rendered) {
                        // Python finished without ever drawing a frame. Do not
                        // leave "Starting Python…" on screen forever: show the
                        // exit code and point at the real error in logcat.
                        postPlaceholder("Python exited with code " + status
                                + " before rendering the UI.\n\n"
                                + "Run `adb logcat -s pymobile.stderr` for the traceback.");
                    } else if (status != 0) {
                        postPlaceholder("Python exited with code " + status
                                + "\n\nRun `adb logcat -s pymobile.stderr` for details.");
                    }
                } catch (Throwable error) {
                    // e.g. System.loadLibrary failed: surface it instead of
                    // leaving the placeholder frozen forever.
                    Log.e(TAG, "python failed to start", error);
                    postPlaceholder("Python failed to start:\n" + error
                            + "\n\nRun `adb logcat -s pymobile` for the full error.");
                }
            }
        }, "python-main").start();
    }

    /** Build the tree off the JSON Python sent us and swap it in. */
    void renderTree(final String json) {
        rendered = true;
        ui.post(new Runnable() {
            @Override
            public void run() {
                try {
                    JSONObject root = new JSONObject(json);
                    View existing = container.getChildCount() == 1
                            ? container.getChildAt(0) : null;
                    // Patch the live views when the structure is unchanged:
                    // this preserves scroll position and keyboard focus.
                    if (existing != null && builder.update(existing, root)) {
                        return;
                    }
                    View view = builder.build(root);
                    container.removeAllViews();
                    container.addView(view, new FrameLayout.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT));
                } catch (Exception error) {
                    Log.e(TAG, "render failed", error);
                    showPlaceholder("Render error:\n" + error);
                }
            }
        });
    }

    /** Show a toast on the UI thread. */
    void showToast(final String message, final boolean longer) {
        ui.post(new Runnable() {
            @Override
            public void run() {
                DeviceServices.toast(MainActivity.this, message, longer);
            }
        });
    }

    /** Replace the content with a plain message (startup and error states). */
    private void showPlaceholder(String message) {
        TextView text = new TextView(this);
        text.setText(message);
        text.setTextColor(Color.parseColor("#444444"));
        text.setPadding(48, 64, 48, 48);
        container.removeAllViews();
        container.addView(text);
    }

    private void postPlaceholder(final String message) {
        ui.post(new Runnable() {
            @Override
            public void run() {
                showPlaceholder(message);
            }
        });
    }

    /**
     * Show a permission dialog and block the calling thread until answered.
     *
     * Called from the Python thread, never from the UI thread.
     */
    static boolean requestPermissionBlocking(final Activity activity, final String permission) {
        // The window must be up before a dialog can be shown.
        try {
            if (!resumedLatch.await(10, TimeUnit.SECONDS)) {
                Log.w(TAG, "activity not resumed; permission dialog may be skipped");
            }
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
        }

        final CountDownLatch latch = new CountDownLatch(1);
        permissionLatch = latch;
        permissionGranted = false;
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                activity.requestPermissions(new String[]{permission}, PERMISSION_REQUEST);
            }
        });
        try {
            // A generous cap: if the user never answers we must not hang forever.
            latch.await(120, TimeUnit.SECONDS);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
        }
        permissionLatch = null;
        return permissionGranted || DeviceServices.hasPermission(activity, permission);
    }

    @Override
    public void onRequestPermissionsResult(
            int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == PERMISSION_REQUEST) {
            permissionGranted = results.length > 0
                    && results[0] == android.content.pm.PackageManager.PERMISSION_GRANTED;
            CountDownLatch latch = permissionLatch;
            if (latch != null) {
                latch.countDown();
            }
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        resumedLatch.countDown();
    }

    /** Route the hardware back button into Python. */
    @Override
    public void onBackPressed() {
        Native.dispatchEvent("", "back", "");
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (instance == this) {
            instance = null;
        }
        Native.stopEventLoop();
    }
}
