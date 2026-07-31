/* PyMobile JNI bridge.
 *
 * Two directions of traffic:
 *
 *   Python → Java   through the built-in module `_pymobile_android`
 *                   (render, toast, vibrate, notify, permissions);
 *   Java   → Python through `Native.dispatchEvent`, which pushes UI events
 *                   into a queue the Python thread blocks on.
 *
 * The Python interpreter runs on its own thread, so every JNI call attaches
 * that thread to the JVM, and `next_event` releases the GIL while waiting.
 */

#include <android/log.h>
#include <errno.h>
#include <jni.h>
#include <pthread.h>
#include <Python.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>

#define TAG "pymobile"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

static JavaVM *g_vm = NULL;
static jclass g_native_class = NULL;

/* ------------------------------------------------------------------ */
/* Event queue: Java UI thread → Python thread                         */
/* ------------------------------------------------------------------ */

typedef struct Event {
    char *widget_id;
    char *type;
    char *value;
    struct Event *next;
} Event;

static Event *q_head = NULL;
static Event *q_tail = NULL;
static pthread_mutex_t q_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t q_cond = PTHREAD_COND_INITIALIZER;
static int q_stopped = 0;

static void queue_push(const char *widget_id, const char *type, const char *value) {
    Event *event = (Event *)calloc(1, sizeof(Event));
    if (!event) {
        return;
    }
    event->widget_id = strdup(widget_id ? widget_id : "");
    event->type = strdup(type ? type : "");
    event->value = strdup(value ? value : "");

    pthread_mutex_lock(&q_mutex);
    if (q_tail) {
        q_tail->next = event;
    } else {
        q_head = event;
    }
    q_tail = event;
    pthread_cond_signal(&q_cond);
    pthread_mutex_unlock(&q_mutex);
}

static void event_free(Event *event) {
    free(event->widget_id);
    free(event->type);
    free(event->value);
    free(event);
}

/* ------------------------------------------------------------------ */
/* Stdio → logcat                                                      */
/* ------------------------------------------------------------------ */

static const int MAX_BYTES_PER_WRITE = 4000;

typedef struct {
    int fd;
    android_LogPriority priority;
    const char *tag;
    int pipe[2];
} StreamInfo;

static StreamInfo STREAMS[] = {
    {STDOUT_FILENO, ANDROID_LOG_INFO, "pymobile.stdout", {-1, -1}},
    {STDERR_FILENO, ANDROID_LOG_WARN, "pymobile.stderr", {-1, -1}},
    {-1, ANDROID_LOG_UNKNOWN, NULL, {-1, -1}},
};

static void *stream_reader(void *arg) {
    StreamInfo *si = (StreamInfo *)arg;
    char buf[MAX_BYTES_PER_WRITE + 1];
    ssize_t count;
    while ((count = read(si->pipe[0], buf, MAX_BYTES_PER_WRITE)) > 0) {
        buf[count] = '\0';
        __android_log_write(si->priority, si->tag, buf);
    }
    return NULL;
}

static void redirect_stdio_to_logcat(void) {
    for (StreamInfo *si = STREAMS; si->tag; si++) {
        FILE *file = (si->fd == STDOUT_FILENO) ? stdout : stderr;
        setvbuf(file, NULL, _IOLBF, 0);
        if (pipe(si->pipe) != 0 || dup2(si->pipe[1], si->fd) == -1) {
            LOGE("stdio redirect failed: %s", strerror(errno));
            return;
        }
        pthread_t thread;
        if (pthread_create(&thread, NULL, stream_reader, si) == 0) {
            pthread_detach(thread);
        }
    }
}

/* ------------------------------------------------------------------ */
/* Helpers for calling static Java methods                             */
/* ------------------------------------------------------------------ */

/* Attach the calling thread and return its JNIEnv. */
static JNIEnv *jni_env(int *attached) {
    JNIEnv *env = NULL;
    *attached = 0;
    if (!g_vm) {
        return NULL;
    }
    if ((*g_vm)->GetEnv(g_vm, (void **)&env, JNI_VERSION_1_6) == JNI_EDETACHED) {
        if ((*g_vm)->AttachCurrentThread(g_vm, &env, NULL) != JNI_OK) {
            LOGE("AttachCurrentThread failed");
            return NULL;
        }
        *attached = 1;
    }
    return env;
}

static void call_void_method(const char *name, const char *signature, ...) {
    int attached = 0;
    JNIEnv *env = jni_env(&attached);
    if (!env || !g_native_class) {
        return;
    }
    jmethodID method = (*env)->GetStaticMethodID(env, g_native_class, name, signature);
    if (!method) {
        LOGE("method not found: %s%s", name, signature);
        (*env)->ExceptionClear(env);
    } else {
        va_list args;
        va_start(args, signature);
        (*env)->CallStaticVoidMethodV(env, g_native_class, method, args);
        va_end(args);
        if ((*env)->ExceptionCheck(env)) {
            (*env)->ExceptionDescribe(env);
            (*env)->ExceptionClear(env);
        }
    }
    if (attached) {
        (*g_vm)->DetachCurrentThread(g_vm);
    }
}

/* ------------------------------------------------------------------ */
/* Built-in module `_pymobile_android`                                 */
/* ------------------------------------------------------------------ */

static PyObject *py_render(PyObject *self, PyObject *args) {
    const char *json;
    (void)self;
    if (!PyArg_ParseTuple(args, "s", &json)) {
        return NULL;
    }
    int attached = 0;
    JNIEnv *env = jni_env(&attached);
    if (env && g_native_class) {
        jstring jjson = (*env)->NewStringUTF(env, json);
        jmethodID method =
            (*env)->GetStaticMethodID(env, g_native_class, "render", "(Ljava/lang/String;)V");
        if (method) {
            (*env)->CallStaticVoidMethod(env, g_native_class, method, jjson);
            if ((*env)->ExceptionCheck(env)) {
                (*env)->ExceptionDescribe(env);
                (*env)->ExceptionClear(env);
            }
        }
        (*env)->DeleteLocalRef(env, jjson);
        if (attached) {
            (*g_vm)->DetachCurrentThread(g_vm);
        }
    }
    Py_RETURN_NONE;
}

/* Generic helper: call a static Java method taking one string. */
static PyObject *call_with_string(const char *name, const char *signature, const char *value,
                                  int extra_bool, int has_bool) {
    int attached = 0;
    JNIEnv *env = jni_env(&attached);
    if (env && g_native_class) {
        jstring jvalue = (*env)->NewStringUTF(env, value);
        jmethodID method = (*env)->GetStaticMethodID(env, g_native_class, name, signature);
        if (method) {
            if (has_bool) {
                (*env)->CallStaticVoidMethod(env, g_native_class, method, jvalue,
                                             (jboolean)extra_bool);
            } else {
                (*env)->CallStaticVoidMethod(env, g_native_class, method, jvalue);
            }
            if ((*env)->ExceptionCheck(env)) {
                (*env)->ExceptionDescribe(env);
                (*env)->ExceptionClear(env);
            }
        }
        (*env)->DeleteLocalRef(env, jvalue);
        if (attached) {
            (*g_vm)->DetachCurrentThread(g_vm);
        }
    }
    Py_RETURN_NONE;
}

static PyObject *py_toast(PyObject *self, PyObject *args) {
    const char *message;
    int longer = 0;
    (void)self;
    if (!PyArg_ParseTuple(args, "s|p", &message, &longer)) {
        return NULL;
    }
    return call_with_string("toast", "(Ljava/lang/String;Z)V", message, longer, 1);
}

static PyObject *py_vibrate(PyObject *self, PyObject *args) {
    long milliseconds = 0;
    (void)self;
    if (!PyArg_ParseTuple(args, "l", &milliseconds)) {
        return NULL;
    }
    call_void_method("vibrate", "(J)V", (jlong)milliseconds);
    Py_RETURN_NONE;
}

static PyObject *py_vibrate_pattern(PyObject *self, PyObject *args) {
    PyObject *sequence;
    int repeat = -1;
    (void)self;
    if (!PyArg_ParseTuple(args, "O|i", &sequence, &repeat)) {
        return NULL;
    }
    Py_ssize_t length = PySequence_Size(sequence);
    if (length < 0) {
        return NULL;
    }
    int attached = 0;
    JNIEnv *env = jni_env(&attached);
    if (env && g_native_class) {
        jlongArray array = (*env)->NewLongArray(env, (jsize)length);
        jlong *values = (jlong *)malloc(sizeof(jlong) * (size_t)length);
        if (!values) {
            (*env)->DeleteLocalRef(env, array);
            if (attached) {
                (*g_vm)->DetachCurrentThread(g_vm);
            }
            PyErr_NoMemory();
            return NULL;
        }
        int ok = 1;
        for (Py_ssize_t i = 0; i < length; i++) {
            PyObject *item = PySequence_GetItem(sequence, i);
            if (!item) {
                ok = 0;
                break;
            }
            long value = PyLong_AsLong(item);
            Py_XDECREF(item);
            if (value == -1 && PyErr_Occurred()) {
                ok = 0;
                break;
            }
            values[i] = (jlong)value;
        }
        if (!ok) {
            free(values);
            (*env)->DeleteLocalRef(env, array);
            if (attached) {
                (*g_vm)->DetachCurrentThread(g_vm);
            }
            return NULL;
        }
        (*env)->SetLongArrayRegion(env, array, 0, (jsize)length, values);
        free(values);
        jmethodID method =
            (*env)->GetStaticMethodID(env, g_native_class, "vibratePattern", "([JI)V");
        if (method) {
            (*env)->CallStaticVoidMethod(env, g_native_class, method, array, (jint)repeat);
            if ((*env)->ExceptionCheck(env)) {
                (*env)->ExceptionClear(env);
            }
        }
        (*env)->DeleteLocalRef(env, array);
        if (attached) {
            (*g_vm)->DetachCurrentThread(g_vm);
        }
    }
    Py_RETURN_NONE;
}

static PyObject *py_cancel_vibration(PyObject *self, PyObject *args) {
    (void)self;
    (void)args;
    call_void_method("cancelVibration", "()V");
    Py_RETURN_NONE;
}

static PyObject *py_notify(PyObject *self, PyObject *args) {
    const char *title;
    const char *body;
    int identifier = 1;
    int ongoing = 0;
    (void)self;
    if (!PyArg_ParseTuple(args, "ssi|p", &title, &body, &identifier, &ongoing)) {
        return NULL;
    }
    int attached = 0;
    JNIEnv *env = jni_env(&attached);
    if (env && g_native_class) {
        jstring jtitle = (*env)->NewStringUTF(env, title);
        jstring jbody = (*env)->NewStringUTF(env, body);
        jmethodID method = (*env)->GetStaticMethodID(
            env, g_native_class, "notify", "(Ljava/lang/String;Ljava/lang/String;IZ)V");
        if (method) {
            (*env)->CallStaticVoidMethod(env, g_native_class, method, jtitle, jbody,
                                         (jint)identifier, (jboolean)ongoing);
            if ((*env)->ExceptionCheck(env)) {
                (*env)->ExceptionClear(env);
            }
        }
        (*env)->DeleteLocalRef(env, jtitle);
        (*env)->DeleteLocalRef(env, jbody);
        if (attached) {
            (*g_vm)->DetachCurrentThread(g_vm);
        }
    }
    Py_RETURN_NONE;
}

static PyObject *py_cancel_notification(PyObject *self, PyObject *args) {
    int identifier;
    (void)self;
    if (!PyArg_ParseTuple(args, "i", &identifier)) {
        return NULL;
    }
    call_void_method("cancelNotification", "(I)V", (jint)identifier);
    Py_RETURN_NONE;
}

static PyObject *py_has_permission(PyObject *self, PyObject *args) {
    const char *permission;
    (void)self;
    if (!PyArg_ParseTuple(args, "s", &permission)) {
        return NULL;
    }
    int granted = 0;
    int attached = 0;
    JNIEnv *env = jni_env(&attached);
    if (env && g_native_class) {
        jstring jperm = (*env)->NewStringUTF(env, permission);
        jmethodID method = (*env)->GetStaticMethodID(env, g_native_class, "hasPermission",
                                                     "(Ljava/lang/String;)Z");
        if (method) {
            granted = (*env)->CallStaticBooleanMethod(env, g_native_class, method, jperm);
            if ((*env)->ExceptionCheck(env)) {
                (*env)->ExceptionClear(env);
                granted = 0;
            }
        }
        (*env)->DeleteLocalRef(env, jperm);
        if (attached) {
            (*g_vm)->DetachCurrentThread(g_vm);
        }
    }
    return PyBool_FromLong(granted);
}

static PyObject *py_device_language(PyObject *self, PyObject *args) {
    (void)self;
    (void)args;
    PyObject *result = NULL;
    int attached = 0;
    JNIEnv *env = jni_env(&attached);
    if (env && g_native_class) {
        jmethodID method = (*env)->GetStaticMethodID(env, g_native_class, "deviceLanguage",
                                                     "()Ljava/lang/String;");
        if (method) {
            jstring value = (jstring)(*env)->CallStaticObjectMethod(env, g_native_class, method);
            if ((*env)->ExceptionCheck(env)) {
                (*env)->ExceptionClear(env);
            } else if (value) {
                const char *utf = (*env)->GetStringUTFChars(env, value, NULL);
                if (utf) {
                    result = PyUnicode_FromString(utf);
                    (*env)->ReleaseStringUTFChars(env, value, utf);
                }
                (*env)->DeleteLocalRef(env, value);
            }
        }
        if (attached) {
            (*g_vm)->DetachCurrentThread(g_vm);
        }
    }
    if (!result) {
        result = PyUnicode_FromString("");
    }
    return result;
}

static PyObject *py_request_permission(PyObject *self, PyObject *args) {
    const char *permission;
    (void)self;
    if (!PyArg_ParseTuple(args, "s", &permission)) {
        return NULL;
    }
    int granted = 0;
    int attached = 0;
    JNIEnv *env = jni_env(&attached);
    if (env && g_native_class) {
        jstring jperm = (*env)->NewStringUTF(env, permission);
        jmethodID method = (*env)->GetStaticMethodID(env, g_native_class, "requestPermission",
                                                     "(Ljava/lang/String;)Z");
        if (method) {
            /* This blocks until the user answers, so release the GIL to keep
               the rest of the interpreter responsive. */
            Py_BEGIN_ALLOW_THREADS
            granted = (*env)->CallStaticBooleanMethod(env, g_native_class, method, jperm);
            Py_END_ALLOW_THREADS
            if ((*env)->ExceptionCheck(env)) {
                (*env)->ExceptionClear(env);
                granted = 0;
            }
        }
        (*env)->DeleteLocalRef(env, jperm);
        if (attached) {
            (*g_vm)->DetachCurrentThread(g_vm);
        }
    }
    return PyBool_FromLong(granted);
}

/* Block until a UI event arrives. Returns (widget_id, type, value) or None. */
static PyObject *py_next_event(PyObject *self, PyObject *args) {
    int timeout_ms = -1;
    (void)self;
    if (!PyArg_ParseTuple(args, "|i", &timeout_ms)) {
        return NULL;
    }

    Event *event = NULL;
    Py_BEGIN_ALLOW_THREADS
    pthread_mutex_lock(&q_mutex);
    if (!q_head && !q_stopped) {
        if (timeout_ms < 0) {
            pthread_cond_wait(&q_cond, &q_mutex);
        } else {
            struct timeval now;
            struct timespec deadline;
            gettimeofday(&now, NULL);
            deadline.tv_sec = now.tv_sec + timeout_ms / 1000;
            deadline.tv_nsec = (now.tv_usec + (timeout_ms % 1000) * 1000) * 1000;
            if (deadline.tv_nsec >= 1000000000L) {
                deadline.tv_sec += 1;
                deadline.tv_nsec -= 1000000000L;
            }
            pthread_cond_timedwait(&q_cond, &q_mutex, &deadline);
        }
    }
    if (q_head) {
        event = q_head;
        q_head = event->next;
        if (!q_head) {
            q_tail = NULL;
        }
    }
    pthread_mutex_unlock(&q_mutex);
    Py_END_ALLOW_THREADS

    if (!event) {
        Py_RETURN_NONE;
    }
    PyObject *result = Py_BuildValue("(sss)", event->widget_id, event->type, event->value);
    event_free(event);
    return result;
}

static PyMethodDef module_methods[] = {
    {"render", py_render, METH_VARARGS, "Send a serialised widget tree to the UI thread."},
    {"toast", py_toast, METH_VARARGS, "Show a toast."},
    {"vibrate", py_vibrate, METH_VARARGS, "Vibrate once."},
    {"vibrate_pattern", py_vibrate_pattern, METH_VARARGS, "Play a vibration pattern."},
    {"cancel_vibration", py_cancel_vibration, METH_NOARGS, "Stop vibrating."},
    {"notify", py_notify, METH_VARARGS, "Post a notification."},
    {"cancel_notification", py_cancel_notification, METH_VARARGS, "Cancel a notification."},
    {"has_permission", py_has_permission, METH_VARARGS, "Check a permission."},
    {"request_permission", py_request_permission, METH_VARARGS, "Request a permission."},
    {"device_language", py_device_language, METH_NOARGS, "The device's language tag."},
    {"next_event", py_next_event, METH_VARARGS, "Block until the next UI event."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef android_module = {
    PyModuleDef_HEAD_INIT, "_pymobile_android", "PyMobile Android platform hooks.", -1,
    module_methods, NULL, NULL, NULL, NULL,
};

static PyObject *init_android_module(void) {
    return PyModule_Create(&android_module);
}

/* ------------------------------------------------------------------ */
/* JNI entry points                                                    */
/* ------------------------------------------------------------------ */

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM *vm, void *reserved) {
    (void)reserved;
    g_vm = vm;
    return JNI_VERSION_1_6;
}

/* Java → Python: queue a UI event. */
JNIEXPORT void JNICALL Java_org_pymobile_app_Native_dispatchEvent(
        JNIEnv *env, jclass clazz, jstring widgetIdJ, jstring typeJ, jstring valueJ) {
    (void)clazz;
    const char *widget_id = (*env)->GetStringUTFChars(env, widgetIdJ, NULL);
    const char *type = (*env)->GetStringUTFChars(env, typeJ, NULL);
    const char *value = valueJ ? (*env)->GetStringUTFChars(env, valueJ, NULL) : "";

    queue_push(widget_id, type, value);

    (*env)->ReleaseStringUTFChars(env, widgetIdJ, widget_id);
    (*env)->ReleaseStringUTFChars(env, typeJ, type);
    if (valueJ) {
        (*env)->ReleaseStringUTFChars(env, valueJ, value);
    }
}

/* Wake the Python thread so it can shut down. */
JNIEXPORT void JNICALL Java_org_pymobile_app_Native_stopEventLoop(JNIEnv *env, jclass clazz) {
    (void)env;
    (void)clazz;
    pthread_mutex_lock(&q_mutex);
    q_stopped = 1;
    pthread_cond_broadcast(&q_cond);
    pthread_mutex_unlock(&q_mutex);
}

JNIEXPORT jint JNICALL
Java_org_pymobile_app_PythonRuntime_startPython(
        JNIEnv *env, jobject obj, jstring homeJ, jstring appDirJ, jstring entryJ) {
    (void)obj;

    const char *home = (*env)->GetStringUTFChars(env, homeJ, NULL);
    const char *app_dir = (*env)->GetStringUTFChars(env, appDirJ, NULL);
    const char *entry = (*env)->GetStringUTFChars(env, entryJ, NULL);

    redirect_stdio_to_logcat();
    LOGI("starting python: home=%s app=%s entry=%s", home, app_dir, entry);

    /* Cache the Native class so background threads can find it: JNI class
     * lookup from a non-Java thread only sees the system class loader. */
    jclass local = (*env)->FindClass(env, "org/pymobile/app/Native");
    if (local) {
        g_native_class = (jclass)(*env)->NewGlobalRef(env, local);
        (*env)->DeleteLocalRef(env, local);
    } else {
        LOGE("org.pymobile.app.Native not found");
        (*env)->ExceptionClear(env);
    }

    if (PyImport_AppendInittab("_pymobile_android", init_android_module) != 0) {
        LOGE("could not register _pymobile_android");
    }

    PyStatus status;
    PyPreConfig preconfig;
    PyPreConfig_InitIsolatedConfig(&preconfig);
    preconfig.utf8_mode = 1;
    status = Py_PreInitialize(&preconfig);
    if (PyStatus_Exception(status)) {
        LOGE("Py_PreInitialize failed");
        return 1;
    }

    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.write_bytecode = 0;
    config.install_signal_handlers = 0;

    wchar_t *whome = Py_DecodeLocale(home, NULL);
    PyConfig_SetString(&config, &config.home, whome);
    wchar_t *argv[] = {L"pymobile", NULL};
    PyConfig_SetArgv(&config, 1, argv);

    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    PyMem_RawFree(whome);
    if (PyStatus_Exception(status)) {
        LOGE("Py_InitializeFromConfig failed: %s", status.err_msg ? status.err_msg : "?");
        return 1;
    }

    char code[4096];
    snprintf(code, sizeof(code),
             "import sys, os\n"
             "sys.path.insert(0, '%s')\n"
             "os.chdir('%s')\n"
             "os.environ['ANDROID_APP_PATH'] = '%s'\n"
             /* OpenSSL looks for its CA bundle at a compiled-in path that does
                not exist on Android; point it at the one shipped in assets so
                HTTPS can verify certificates. */
             "_ca = os.path.join('%s', 'etc', 'ssl', 'cert.pem')\n"
             "if os.path.exists(_ca):\n"
             "    os.environ['SSL_CERT_FILE'] = _ca\n"
             "    os.environ['REQUESTS_CA_BUNDLE'] = _ca\n",
             app_dir, app_dir, app_dir, home);
    if (PyRun_SimpleString(code) != 0) {
        LOGE("failed to configure sys.path");
    }

    /* The launcher passes the entry name (the prebuilt dex historically
     * hard-codes "main.py"). With optimize=true only main.pyc exists, so fall
     * back to the sibling file (main.py <-> main.pyc) before running. */
    char runner[4096];
    snprintf(runner, sizeof(runner),
             "import runpy, sys, os, traceback\n"
             "_entry = '%s'\n"
             "_path = os.path.join('%s', _entry)\n"
             "if not os.path.exists(_path):\n"
             "    _alt = _entry + 'c' if not _entry.endswith('.pyc') else _entry[:-1]\n"
             "    if os.path.exists(os.path.join('%s', _alt)):\n"
             "        _path = os.path.join('%s', _alt)\n"
             "try:\n"
             "    runpy.run_path(_path, run_name='__main__')\n"
             "except SystemExit:\n"
             "    pass\n"
             "except BaseException:\n"
             "    traceback.print_exc()\n"
             "    sys.stderr.flush()\n",
             entry, app_dir, app_dir, app_dir);

    int rc = PyRun_SimpleString(runner);
    LOGI("python finished with rc=%d", rc);

    (*env)->ReleaseStringUTFChars(env, homeJ, home);
    (*env)->ReleaseStringUTFChars(env, appDirJ, app_dir);
    (*env)->ReleaseStringUTFChars(env, entryJ, entry);

    Py_Finalize();
    return rc;
}
