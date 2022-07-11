#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdbool.h>

#include "_hashmap.h"

/* --------------------------- Definitions --------------------------------- */

#define HASHSET_VALUE 0

/* -------------------------- Helper Types --------------------------------- */

/*
 * Data for the leaves (routes) of the trie.
 */
typedef struct RouteMap_LeafData {
    PyObject* path_parameters;
    PyObject* asgi_handlers;
    bool is_asgi;
    char* static_path;
} RouteMap_LeafData;

static void
RouteMap_LeafData_free(RouteMap_LeafData* data)
{
    if (data == NULL)
        return;

    /* Decrement refcount for python objects. */
    Py_XDECREF(data->path_parameters);
    Py_XDECREF(data->asgi_handlers);

    /* Free string */
    PyMem_Free(data->static_path);

    /* Free the data */
    PyMem_Free(data);
}

/*
 * The actual trie.
 */
typedef struct RouteMap_Tree {
    hashmap* children; // dict[str, RouteMap_Tree]
    RouteMap_LeafData* data;
} RouteMap_Tree;

/*
 * Create a new trie.
 */
static RouteMap_Tree*
RouteMap_Tree_create()
{
    RouteMap_Tree* tree;

    tree = (RouteMap_Tree*)PyMem_Malloc(sizeof(RouteMap_Tree));
    if (tree == NULL)
        return (RouteMap_Tree*)PyErr_NoMemory(); /* Always returns NULL */

    tree->children = hashmap_create();
    tree->data = NULL;

    return tree;
}

/*
 * Free the memory allocated to a trie.
 */
static void
RouteMap_Tree_free(RouteMap_Tree* tree)
{
    if (tree == NULL)
        return;

    /* Free children */
    // TODO: Recursively decend down trie

    /* Free data */
    PyMem_Free(tree->data);

    /* Free the tree itself. */
    PyMem_Free(tree);
}

/* -------------------------- Custom Types --------------------------------- */

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
 * RouteMap.__new__(self, *args, **kwargs);
 *
 * Initializes (allocates) the fields in the RouteMap object.
 */
static PyObject*
RouteMap_new(PyTypeObject* type, PyObject* args, PyObject* kwds)
{
    RouteMap* self;

    self = (RouteMap*)type->tp_alloc(type, 0);
    if (self == NULL) {
        return (PyObject*)self;
    }

    self->static_paths = hashset_create();
    self->plain_routes = hashmap_create();
    self->tree = RouteMap_Tree_create();

    return (PyObject*)self;
}


/*
 * RouteMap.__del__();
 *
 * Frees memory in the RouteMap object.
 */
static void
RouteMap_dealloc(RouteMap* self)
{
    /* Free keys in static_paths hashset */
    // TODO Free every key in `static_paths`

    /* Free keys and leaves in `plain_routes` */
    // TODO Free every key and leaf in `plain_routes`

    /* Free trie. */
    RouteMap_Tree_free(self->tree);

    /* Free type object. */
    Py_TYPE(self)->tp_free((PyObject*)self);
}
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
    .tp_new = RouteMap_new,
    .tp_dealloc = (destructor)RouteMap_dealloc,
};

/* ------------------------ Module Definition ------------------------------ */

/*
 * Defines the contents of the module.
 */
static PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_route_map",
    .m_doc = PyDoc_STR("Native version of Starlite's RouteMap"),
    .m_size = -1,
};

/*
 * Module initializer
 *
 * Allocates, creates, and adds types to the module.
 */
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
