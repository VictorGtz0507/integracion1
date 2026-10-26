1. Necesito crear una nueva vista dentro de mi aplicacion de Electron,
esta vista de electron lo que tiene como objetivo es interactuar con
ollama en mi docker, que tiene dentro deepseek-coder.

2. Deepseek debe ser capaz de interactuar con mi biblioteca, es decir
debe describirme los libros que tengo en mi biblioteca solamente, de no tenerlo es mejor mencionar que no lo tiene y ofrecer algo mas.

3. Crea la nueva vista que tenga una conexion a mi docker, a partir
de esto, con un curl https://localhost:11434/api/chat -d predefinido, la aplicacion debe de mandar ese mismo mensaje juntoa un json del texto que se haya entregado por el usuario.

4. El electron debe recibir la respuesta de parte de la llm y mostrarla dentro de la pagina.