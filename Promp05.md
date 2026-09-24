Desarrollar un microservicio independiente de autenticación y gestión básica de usuarios para la plataforma de librería en línea existente. El servicio deberá desarrollarse con Python, Flask, Psycopg 3 y PostgreSQL, utilizar la base de datos actual del proyecto y exponer sus respuestas tanto en XML como en JSON.

1.- quiero que crees un microservicio de login, este microservicio de login al crearlo y generarlo no debe de afectar mi demas arquitectura

1.2-Crea el microservicio en el directorio apps/services/login

1.3- Modifica e integra las tablas necesarias a la base de datos library sin afectar las demas tablas utilizadas

2.- Despliega el microservicio en el puerto 5000

2.1-Utiliza Swagger para documentar los endpoints en XML y JSON

3.- es necesario que el microservicio se capaz de lo siguiente

POST

/register

Registrar un nuevo usuario

POST

/login

Autenticar al usuario e iniciar sesión

POST

/logout

Cerrar la sesión

GET

/session

Consultar si existe una sesión autenticada

GET

/health

Verificar el estado del microservicio y PostgreSQL

4.- los endpoints deberán soportar: ?format=xml y ?format=json, si no se especifica el parámetro format, XML será el formato predeterminado

5.- El microservicio debe solicitar para el registro los siguientes datos

nombre apellido paterno apellido materno email password

6.- El correo deberá validarse antes de registrarse y deberá ser único. La contraseña nunca deberá almacenarse en texto plano. El sistema almacenará únicamente un hash seguro de la contraseña.

7.- La autenticación deberá verificar las credenciales contra PostgreSQL y, cuando sean correctas, crear una sesión del lado de Flask que permita identificar al usuario en solicitudes posteriores.