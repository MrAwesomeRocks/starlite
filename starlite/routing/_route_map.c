#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>

#include <stdbool.h>
#include <string.h>

#include "_hashmap.h"

/* --------------------------- Definitions --------------------------------- */

#define HASHSET_VALUE 0

/* -------------------------- Helper Funcs --------------------------------- */

/*
 * Allocate and copy string.
 *
 * Must be freed with PyMem_Free!
 */
static char*
strdup_p(const char* src)
{
    size_t len = strlen(src) + 1; /* Null terminator */

    /* Allocate dest pointer. */
    char* dest = PyMem_Malloc(len);
    if (dest == NULL)
        return (char*)PyErr_NoMemory(); /* Always returns NULL */

    /* Copy string */
    memcpy(dest, src, len);

    return dest;
}

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
 * RouteMap._add_node(self, route: BaseRoute, app: "Starlite") -> _RouteMapTree;
 *
 * Adds a new route path (e.g. '/foo/bar/{param:int}') into the route_map tree.
 *
 * Inserts non-parameter paths ('plain routes') off the tree's root node.
 * For paths containing parameters, splits the path on '/' and nests each path
 * segment under the previous segment's node (see prefix tree / trie).
 */
static RouteMap_Tree*
RouteMap__add_node(RouteMap* self, PyObject* route, PyObject* app)
{
    // Read fields
    PyObject* py_path = PyObject_GetAttrString(route, "path");
    PyObject* path_params = PyObject_GetAttrString(route, "path_parameters");

    // Check fields
    if (py_path == NULL || !PyUnicode_Check(py_path) ||       // Valid string
        path_params == NULL || !PySequence_Check(path_params) // Valid list
    ) {
        PyErr_SetString(PyExc_TypeError, "Invalid route.");
        return NULL;
    }

    // Get path
    Py_ssize_t path_size;
    char* path = strdup_p(PyUnicode_AsUTF8AndSize(py_path, &path_size));

    /* Get the trie node for the path.
     *
     * First, check if its a plain path.
     */
    RouteMap_Tree* cur_node;
    if (PySequence_Length(path_params) != 0 ||
        hashset_contains(self->static_paths, path, path_size)) {
        /* Replace path params with "*" */
        // TODO

        /* Iterate down tree with components. */
        cur_node = self->tree;
        // TODO
    } else {
        // Try to read plain path from dict
        bool in_map = hashmap_get(self->plain_routes, path, path_size,
                                  (uintptr_t*)&cur_node);

        // If not read, then add
        if (!in_map) {
            cur_node = (RouteMap_Tree*)PyMem_Malloc(sizeof(RouteMap_Tree));
            hashmap_set(self->plain_routes, path, path_size,
                        (uintptr_t)cur_node);
        }
    }

    // TODO configure node
    // RouteMap__configure_node(route, cur_node, app);
    return cur_node;
}

/*
 * RouteMap.add_routes(self, routes: Collection[BaseRoute], app: "Starlite");
 *
 * Add routes to the RouteMap.
 */
static PyObject*
RouteMap_add_routes(RouteMap* self, PyObject* args, PyObject* kwds)
{
    PyObject* routes;
    PyObject* app;
    static char* kwlist[] = {"routes", "app", NULL};

    // Parse args
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "OO", kwlist, &routes, &app))
        return NULL;

    // Check types of args
    if (app == NULL ||
        !PyObject_HasAttrString(app, "build_route_middleware_stack")) {
        PyErr_SetString(PyExc_TypeError, "App must be a starlite instance.");
        return NULL;
    }

    PyObject* routes_iter = PyObject_GetIter(routes);
    if (routes == NULL || routes_iter == NULL) {
        PyErr_SetString(PyExc_TypeError, "Routes must be an iterable.");
        return NULL;
    }

    PyObject* route;
    while ((route = PyIter_Next(routes_iter))) {
        RouteMap_Tree* node = RouteMap__add_node(self, route, app);
        Py_DECREF(route);

        if (node == NULL)
            break;
    }
    Py_DECREF(routes_iter);

    if (PyErr_Occurred())
        return NULL;
    Py_RETURN_NONE;
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
 * RouteMap method definition. table
 */
static PyMethodDef RouteMap_methods[] = {
    {"add_routes", (PyCFunctionWithKeywords)RouteMap_add_routes,
     METH_VARARGS | METH_KEYWORDS,
     PyDoc_STR("RouteMap.add_routes(self, routes: Collection[BaseRoute], "
               "app: Starlite)\n\n"
               "Adds a new route path (e.g. '/foo/bar/{param:int}') into "
               "the route_map tree.\n\n"
               "Inserts non-parameter paths ('plain routes') off the "
               "tree's root node.\n"
               "For paths containing parameters, splits the path on '/' "
               "and nests each path.\n"
               "segment under the previous segment's node (see prefix tree "
               "/ trie).")},
    {NULL}, /* Sentinel */
};

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
    .tp_methods = RouteMap_methods,
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
