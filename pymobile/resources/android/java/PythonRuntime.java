package org.pymobile.app;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.res.AssetManager;
import android.util.Log;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Extracts the bundled Python runtime and application code, then starts the
 * interpreter through JNI.
 *
 * Assets are unpacked once per installed versionCode into the app's private
 * storage, because CPython needs a real filesystem for its standard library.
 * The stamp file records that version so an upgrade (Play / adb install -r)
 * re-extracts instead of keeping stale Python on disk.
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
            String version = currentVersionStamp(context);
            if (!version.equals(readStamp(stamp))) {
                Log.i(TAG, "extracting runtime for version " + version + "…");
                deleteRecursively(root);
                extractAssetDir(context.getAssets(), "python", root);
                extractAssetDir(context.getAssets(), "app", root);
                writeStamp(stamp, version);
                Log.i(TAG, "extraction finished");
            }
            File home = new File(root, "python");
            File appDir = new File(root, "app");
            File cert = new File(home, "etc/ssl/cert.pem");
            if (cert.isFile()) {
                // Visible from Java; the JNI bootstrap also exports SSL_CERT_FILE
                // into the interpreter environment so urllib/OpenSSL find the bundle.
                System.setProperty("javax.net.ssl.trustStore", cert.getAbsolutePath());
            }
            return new PythonRuntime().startPython(
                    home.getAbsolutePath(), appDir.getAbsolutePath(), entrypoint);
        } catch (IOException error) {
            Log.e(TAG, "failed to prepare the Python runtime", error);
            return 1;
        }
    }

    /** versionCode of the installed APK, used as the extraction stamp. */
    private static String currentVersionStamp(Context context) {
        try {
            PackageInfo info = context.getPackageManager()
                    .getPackageInfo(context.getPackageName(), 0);
            long code;
            if (android.os.Build.VERSION.SDK_INT >= 28) {
                code = info.getLongVersionCode();
            } else {
                code = info.versionCode;
            }
            return Long.toString(code);
        } catch (PackageManager.NameNotFoundException error) {
            return "unknown";
        }
    }

    private static String readStamp(File stamp) {
        if (!stamp.isFile()) {
            return "";
        }
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new FileInputStream(stamp), StandardCharsets.UTF_8))) {
            String line = reader.readLine();
            return line == null ? "" : line.trim();
        } catch (IOException error) {
            return "";
        }
    }

    private static void writeStamp(File stamp, String version) throws IOException {
        File parent = stamp.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IOException("cannot create " + parent);
        }
        try (OutputStream output = new FileOutputStream(stamp)) {
            output.write(version.getBytes(StandardCharsets.UTF_8));
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
