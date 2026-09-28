Retomamos los microservicios de la libreria en linea: login (register/login/logout/session/health) y book(catalogo de libros, con el esquema de bases de datos que tenemos en postgres)

dentro del microservicio de book, necesitamos proteger las acciones dentro del servicio book (POST,PUT,PATCH,DELETE) exigiendo un JWT valido emitido por el servicio login.
con esto considerado no se puede hacer uso de alg:no

en books debemos mantener publico GET /api/books y GET /api/books/{isbn}   estas acciones no requieren un token; cualquiera debe tener capacidad de consultar este caralogo

en books existen acciones de crear, actualizar o eliminar libros, estos requieren de authorization: Bearer<token>