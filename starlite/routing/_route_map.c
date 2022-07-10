#define PY_SSIZE_T_CLEAN
#include <Python.h>

/* -------------------------- Custom Types --------------------------------- */

/*
 * class RouteMap():
 */
typedef struct RouteMap {
    PyObject_HEAD
} RouteMap;

/*
 * Type defintion
 */
static PyTypeObject RouteMapType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "starlite.routing._route_map.RouteMap",
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
    PyObject *m;
    if (PyType_Ready(&RouteMapType) < 0)
        return NULL;

    m = PyModule_Create(&module_def);
    if (m == NULL)
        return NULL;

    Py_INCREF(&RouteMapType);
    if (PyModule_AddObject(m, "RouteMap", (PyObject *)&RouteMapType) < 0) {
        Py_DECREF(&RouteMapType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
