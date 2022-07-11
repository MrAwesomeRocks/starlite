#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdbool.h>

#include "_hashmap.h"

/* --------------------------- Definitions --------------------------------- */

#define HASHSET_VALUE 0

/* -------------------------- Custom Types --------------------------------- */

/*
 * Data for the leaves (routes) of the trie.
 */
typedef struct RouteMap_LeafData {
    PyObject* path_parameters;
    PyObject* asgi_handlers;
    bool is_asgi;
    char* static_path;
} RouteMap_LeafData;

/*
 * The actual trie.
 */
typedef struct RouteMap_Tree {
    hashmap* children; // dict[str, RouteMap_Tree]
    RouteMap_LeafData* data;
} RouteMap_Tree;

/*
 * class RouteMap():
 */
/* clang-format off */
typedef struct RouteMap {
    PyObject_HEAD
    hashset* static_paths;
    /* clang-format on */
    hashmap* plain_routes; // dict[str, RouteMap_Tree]
    RouteMap_Tree* tree;
} RouteMap;

/*
 * RouteMap type defintion
 */
/* clang-format off */
static PyTypeObject RouteMapType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "starlite.routing._route_map.RouteMap",
    /* clang-format on */
    .tp_doc = PyDoc_STR("Native Starlite RouteMap"),
    .tp_basicsize = sizeof(RouteMap),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = PyType_GenericNew,
};

/* ------------------------ Module Definition ------------------------------ */

static PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_route_map",
    .m_doc = PyDoc_STR("Native version of Starlite's RouteMap"),
    .m_size = -1,
};

PyMODINIT_FUNC
PyInit__route_map(void)
{
    PyObject* m;
    if (PyType_Ready(&RouteMapType) < 0)
        return NULL;

    m = PyModule_Create(&module_def);
    if (m == NULL)
        return NULL;

    Py_INCREF(&RouteMapType);
    if (PyModule_AddObject(m, "RouteMap", (PyObject*)&RouteMapType) < 0) {
        Py_DECREF(&RouteMapType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
