// c:\Users\Equipo z\Desktop\SIIP\static\script.js

// Obtener referencias a los elementos del DOM
const chatbox = document.getElementById('chatbox');
const messageInput = document.getElementById('message');
const userInputDiv = document.getElementById('userInput'); // Contenedor del input y botón

// Función para añadir un mensaje al chatbox
function addMessage(sender, message, messageClass) {
    const messageElement = document.createElement('p');
    messageElement.innerHTML = `<strong>${sender}:</strong> `; // Añadir el remitente primero

    if (sender === "Bot") {
        messageElement.innerHTML += message; // Añadir como HTML para el Bot para renderizar enlaces
    } else {
        messageElement.appendChild(document.createTextNode(message)); // Añadir como texto seguro para el Usuario/Error
    }

    if (messageClass) {
        messageElement.classList.add(messageClass);
    }
    chatbox.appendChild(messageElement);
    // Hacer scroll hacia abajo automáticamente
    chatbox.scrollTop = chatbox.scrollHeight;
}

// Función para enviar el mensaje al backend
async function sendMessage() {
    const message = messageInput.value.trim(); // Obtener y limpiar el mensaje

    if (message === "") {
        return; // No enviar mensajes vacíos
    }

    // Mostrar el mensaje del usuario inmediatamente
    addMessage("Tú", message, "user-message");

    // Limpiar el campo de entrada
    messageInput.value = "";

    try {
        // Enviar el mensaje al servidor usando fetch API
        const response = await fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message }), // Enviar como JSON
        });

        const data = await response.json(); // Esperar la respuesta JSON del servidor
        addMessage("Bot", data.reply, "bot-message"); // Llamar a addMessage para el bot

    } catch (error) {
        console.error("Error al enviar mensaje:", error);
        addMessage("Error", "No se pudo conectar con el servidor.", "bot-message");
    }
}

// Permitir enviar mensaje presionando Enter en el campo de texto
messageInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Cargar historial al iniciar (opcional, si quieres que se cargue al refrescar)
// async function loadHistory() {
//     try {
//         const response = await fetch('/get_history');
//         if (response.ok) {
//             const data = await response.json();
//             chatbox.innerHTML = ''; // Limpiar chatbox antes de cargar
//             data.history.forEach(line => {
//                 const parts = line.split(': ');
//                 const sender = parts[0];
//                 const messageText = parts.slice(1).join(': ');
//                 let messageClass = '';
//                 if (sender === 'Tú' || sender === 'Usuario') { // Ajusta si usas 'Usuario' en el historial de sesión
//                     messageClass = 'user-message';
//                 } else if (sender === 'Sucre' || sender === 'Bot') { // Ajusta si usas 'Sucre' en el historial de sesión
//                     messageClass = 'bot-message';
//                 }
//                 addMessage(sender, messageText, messageClass);
//             });
//         } else {
//             console.error("Error al cargar historial:", response.statusText);
//         }
//     } catch (error) {
//         console.error("Error de red al cargar historial:", error);
//     }
// }

// Descomenta la siguiente línea si quieres cargar el historial al iniciar
// window.onload = loadHistory;
