1.- Instalar docker desktop
2.- Ejecutar docker desktop
3.- abrir terminal y ejecutar:
    docker --version
    docker info
    docker ps
4.- docker pull ollama/ollama:latest
5.- docker images

1.- ejecutar Docker Desktop
2.- crear y ejecutar ollama con almacenamiento persistente 
    docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama/ollama:latest
3.- verificar que el contenedor este ejecutandose en docker ps
4.- utilizando curl o su navegador vamos a verificar si ya podemos el api rest curl http://localhost:11434/pi/tags
5.- vamos a descargar un llm para ejecutarlo en nuestro equipo
    docker exec -it ollama ollama pull deepseek-coder
6.- verificamos el modelo o modelos instalados en ollama
    docker exec -it ollama ollama list
7.- ejecutamos el modelo llm en nuestro contenedor de ollama    docker exec -it ollama ollama run deepseek-coder
8.- finalmente, podemos probar deepseek dentro de docker desjtio o en consola con curl curl https://localhost:11434/api/chat -d "{\"model\":\"deepseek-coder\",\"message\":[{\"role\":\"user\",\"content\":\"ya esta instalado mi llm?\"}],\"stream\":false}"


1. curl https://localhost:11434/api/chat -d "{\"model\":\"deepseek-coder\",\"message\":[{\"role\":\"user\",\"content\":\"hola, que es un arreglo en programacion?\"}],\"stream\":false}"
1. curl https://localhost:11434/api/chat -d "{\"model\":\"deepseek-coder\","message":[{\"role\":\"user\",\"content\":\"hola, que es un arreglo en programacion?"\}],\"stream":false}" 