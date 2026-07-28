package org.pymobile.app;

import android.content.Context;
import android.content.res.AssetManager;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * Extracts the bundled Python runtime and application code, then starts the
 * interpreter through JNI.
 *
 * Assets are unpacked once per version into the app's private storage, because
 * CPython needs a real filesystem for its standard library.
 */
public class PythonRuntime {

    private static final String TAG = "pymobile";
    private static boolean started = false;

    static {
        System.loadLibrary("pymobile");
    }

    private native int startPython(String home, String appDir, String entrypoint);

    /** Extract assets if needed and run the entry point on the calling thread. */
    public static synchronized int run(Context context, String entrypoint) {
        if (started) {
            Log.w(TAG, "Python runtime already started");
            return 0;
        }
        started = true;
        try {
            File root = new File(context.getFilesDir(), "pymobile");
            File stamp = new File(root, ".extracted");
            if (!stamp.exists()) {
                Log.i(TAG, "extracting runtime…");
                deleteRecursively(root);
                extractAssetDir(context.getAssets(), "python", root);
                extractAssetDir(context.getAssets(), "app", root);
                new FileOutputStream(stamp).close();
                Log.i(TAG, "extraction finished");
            }
            File home = new File(root, "python");
            File appDir = new File(root, "app");
            return new PythonRuntime().startPython(
                    home.getAbsolutePath(), appDir.getAbsolutePath(), entrypoint);
        } catch (IOException error) {
            Log.e(TAG, "failed to prepare the Python runtime", error);
            return 1;
        }
    }

    /** Recursively copy an asset directory into the private filesystem. */
    private static void extractAssetDir(AssetManager assets, String path, File targetRoot)
            throws IOException {
        String[] entries = assets.list(path);
        File target = new File(targetRoot, path);
        if (entries == null || entries.length == 0) {
            copyAsset(assets, path, target);
            return;
        }
        if (!target.exists() && !target.mkdirs()) {
            throw new IOException("cannot create " + target);
        }
        for (String name : entries) {
            extractAssetDir(assets, path + "/" + name, targetRoot);
        }
    }

    /** Copy a single asset file. */
    private static void copyAsset(AssetManager assets, String path, File target)
            throws IOException {
        File parent = target.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IOException("cannot create " + parent);
        }
        try (InputStream input = assets.open(path);
             OutputStream output = new FileOutputStream(target)) {
            byte[] buffer = new byte[16384];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
        }
    }

    /** Remove a directory tree. */
    private static void deleteRecursively(File file) {
        File[] children = file.listFiles();
        if (children != null) {
            for (File child : children) {
                deleteRecursively(child);
            }
        }
        file.delete();
    }
}
