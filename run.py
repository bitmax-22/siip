from app import create_app # Importar la fábrica desde el paquete 'app'

app = create_app()

if __name__ == '__main__':
    # Cambiar debug a False para producción
    app.run(debug=True, host='0.0.0.0')