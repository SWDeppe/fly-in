#include <pthread.h>
#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    const char *map_path;
    int width;
    int height;
    int create_window;
    int worker_id;
    PyObject *framebuffers;
    char message[256];
    int status;
} worker_ctx_t;

static PyObject *import_runtime_module(void) {
    PyObject *module_name = PyUnicode_FromString("src.orcestrator.runtime");
    PyObject *module = PyImport_Import(module_name);
    Py_DECREF(module_name);
    return module;
}

static void *worker_thread(void *arg) {
    worker_ctx_t *ctx = (worker_ctx_t *)arg;
    fprintf(stdout, "[thread %d] starting\n", ctx->worker_id);
    fflush(stdout);
    PyGILState_STATE gil = PyGILState_Ensure();

    PyObject *module = import_runtime_module();
    if (module == NULL) {
        PyErr_Print();
        ctx->status = 1;
        PyGILState_Release(gil);
        return NULL;
    }

    PyObject *result = NULL;
    if (ctx->worker_id == 0) {
        PyObject *path = PyUnicode_FromString(ctx->map_path);
        PyObject *func = PyObject_GetAttrString(module, "parse_map_file");
        result = PyObject_CallOneArg(func, path);
        Py_DECREF(func);
        Py_DECREF(path);
    } else {
        PyObject *func = PyObject_GetAttrString(module, "render_framebuffer_from_data");
        PyObject *framebuffer_name = PyUnicode_FromString(ctx->worker_id == 1 ? "primary" : "back");
        result = PyObject_CallFunctionObjArgs(func, framebuffer_name, ctx->framebuffers, NULL);
        Py_DECREF(framebuffer_name);
        Py_DECREF(func);
    }

    if (result != NULL) {
        PyObject *repr = PyObject_Repr(result);
        if (repr != NULL) {
            const char *text = PyUnicode_AsUTF8(repr);
            if (text != NULL) {
                snprintf(ctx->message, sizeof(ctx->message), "%s", text);
            }
            Py_DECREF(repr);
        }
        Py_DECREF(result);
    } else {
        PyErr_Print();
        ctx->status = 1;
    }

    Py_DECREF(module);
    PyGILState_Release(gil);
    return NULL;
}

int main(int argc, char **argv) {
    // set the general rules from args
    const char *map_path = argc > 1 ? argv[1] : "maps/easy/01_linear_path.txt";
    int width = argc > 2 ? atoi(argv[2]) : 800;
    int height = argc > 3 ? atoi(argv[3]) : 600;
    int create_window = argc > 4 ? atoi(argv[4]) : 0;

    // init python
    Py_Initialize();
    PyEval_InitThreads();


    PyGILState_STATE gil = PyGILState_Ensure();

    PyObject *sys_path = PySys_GetObject("path");
    PyObject *cwd = PyUnicode_FromString(".");
    if (sys_path != NULL) {
        PyList_Insert(sys_path, 0, cwd);
    }
    Py_DECREF(cwd);
    PyObject *module = import_runtime_module();
    PyObject *func = module != NULL ? PyObject_GetAttrString(module, "prepare_window") : NULL;
    PyObject *path = PyUnicode_FromString(map_path);
    PyObject *width_obj = PyLong_FromLong(width);
    PyObject *height_obj = PyLong_FromLong(height);
    PyObject *create_obj = PyBool_FromLong(create_window);
    PyObject *kwargs = PyDict_New();
    PyDict_SetItemString(kwargs, "width", width_obj);
    PyDict_SetItemString(kwargs, "height", height_obj);
    PyDict_SetItemString(kwargs, "create_window", create_obj);

    PyObject *framebuffers = NULL;
    if (func != NULL) {
        PyObject *args = PyTuple_Pack(1, path);
        framebuffers = PyObject_Call(func, args, kwargs);
        Py_DECREF(args);
    }
    if (framebuffers == NULL) {
        PyErr_Print();
        PyGILState_Release(gil);
        Py_Finalize();
        return 1;
    }

    Py_DECREF(func);
    Py_DECREF(module);
    Py_DECREF(path);
    Py_DECREF(width_obj);
    Py_DECREF(height_obj);
    Py_DECREF(create_obj);
    Py_DECREF(kwargs);
    PyGILState_Release(gil);

    pthread_t parser_thread, primary_thread, back_thread;
    worker_ctx_t parser_ctx = {map_path, width, height, create_window, 0, NULL, {0}, 0};
    worker_ctx_t primary_ctx = {map_path, width, height, create_window, 1, framebuffers, {0}, 0};
    worker_ctx_t back_ctx = {map_path, width, height, create_window, 2, framebuffers, {0}, 0};
    
    pthread_create(&parser_thread, NULL, worker_thread, &parser_ctx);
    pthread_create(&primary_thread, NULL, worker_thread, &primary_ctx);
    pthread_create(&back_thread, NULL, worker_thread, &back_ctx);
    
    pthread_join(parser_thread, NULL);
    pthread_join(primary_thread, NULL);
    pthread_join(back_thread, NULL);

    PyGILState_STATE finalize_gil = PyGILState_Ensure();
    fprintf(stdout, "parser: %s\n", parser_ctx.message[0] ? parser_ctx.message : "done");
    fprintf(stdout, "primary: %s\n", primary_ctx.message[0] ? primary_ctx.message : "done");
    fprintf(stdout, "back: %s\n", back_ctx.message[0] ? back_ctx.message : "done");
    fflush(stdout);

    Py_DECREF(framebuffers);
    PyGILState_Release(finalize_gil);
    Py_Finalize();
    return 0;
}
