import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Import des Blueprints depuis le dossier 'routes'
from routes.translate import translate_bp
from routes.speak import speak_bp
from routes.languages import languages_bp

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('kumajala.log')
    ]
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement depuis un fichier .env
load_dotenv()


def create_app():
    """
    Crée et configure l'application Flask.
    
    Returns:
        Flask: Instance de l'application Flask configurée
    """
    app = Flask(__name__)
    
    # Configuration CORS pour permettre les requêtes depuis le frontend
    # En développement, autoriser localhost:5173 (Vue.js dev server)
    # En production, ajuster selon votre domaine
    cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')
    CORS(app, 
         origins=cors_origins,
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         allow_headers=['Content-Type', 'Authorization'],
         supports_credentials=True
    )
    
    # Configuration de l'application Flask
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'kumajala-secret-key-default-change-me')
    app.config['DEBUG'] = os.getenv('FLASK_ENV', 'development') == 'development'
    app.config['JSON_AS_ASCII'] = False  # Support des caractères UTF-8
    app.config['JSON_SORT_KEYS'] = False  # Préserver l'ordre des clés JSON
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size
    
    # Log de la configuration au démarrage
    logger.info("=" * 60)
    logger.info("🌍 KUMAJALA API - Démarrage de l'application")
    logger.info("=" * 60)
    logger.info(f"Environnement: {app.config['DEBUG'] and 'DEVELOPMENT' or 'PRODUCTION'}")
    logger.info(f"CORS Origins: {cors_origins}")
    logger.info(f"Firestore: {'LOCAL' if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS') else 'CLOUD'}")
    logger.info(f"Gemini API: {'DISPONIBLE' if os.getenv('GEMINI_API_KEY') else 'NON CONFIGURÉE'}")
    logger.info("=" * 60)
    
    # Enregistrement des blueprints
    app.register_blueprint(translate_bp, url_prefix='/kumajala-api/v1')
    app.register_blueprint(speak_bp, url_prefix='/kumajala-api/v1')
    app.register_blueprint(languages_bp, url_prefix='/kumajala-api/v1')
    
    logger.info("✅ Blueprints enregistrés: translate, speak, languages")
    
    # Route de base pour tester l'API et fournir des informations
    @app.route('/')
    def home():
        """
        Endpoint racine fournissant des informations sur l'API.
        
        Returns:
            JSON: Informations générales et liste des endpoints disponibles
        """
        return jsonify({
            'success': True,
            'message': 'KUMAJALA API - Valorisation des langues Africaines',
            'version': '1.0.0',
            'status': 'running',
            'endpoints': {
                'translation': {
                    'single': '/kumajala-api/v1/translate',
                    'batch': '/kumajala-api/v1/translate/batch',
                    'manage': '/kumajala-api/v1/translations/manage',
                    'search': '/kumajala-api/v1/translations/search'
                },
                'speech': {
                    'synthesize': '/kumajala-api/v1/speak',
                    'languages': '/kumajala-api/v1/speak/languages',
                    'alternatives': '/kumajala-api/v1/speak/alternatives',
                    'check': '/kumajala-api/v1/speak/check-language',
                    'cache_stats': '/kumajala-api/v1/speak/cache/stats',
                    'cache_clear': '/kumajala-api/v1/speak/cache/clear'
                },
                'languages': {
                    'list': '/kumajala-api/v1/languages',
                    'details': '/kumajala-api/v1/languages/<code>',
                    'translations': '/kumajala-api/v1/languages/<code>/translations',
                    'cache_stats': '/kumajala-api/v1/languages/cache/stats',
                    'cache_clear': '/kumajala-api/v1/languages/cache/clear'
                }
            },
            'supported_languages': ['bété', 'baoulé', 'mooré', 'agni', 'fr'],
            'documentation': 'https://github.com/votre-user/kumajala/blob/main/README.md'
        }), 200
    
    # Route de santé pour monitoring
    @app.route('/health')
    def health_check():
        """
        Endpoint de santé pour vérifier le statut de l'API.
        Utilisé par les systèmes de monitoring et load balancers.
        
        Returns:
            JSON: Statut de santé de l'application et de ses services
        """
        try:
            # Import des services pour vérifier leur disponibilité
            from services.firestore import FirestoreService
            from services.gemini import GeminiService
            from services.tts import TTSService
            
            firestore_service = FirestoreService()
            gemini_service = GeminiService()
            tts_service = TTSService()
            
            health_status = {
                'status': 'healthy',
                'services': {
                    'firestore': {
                        'available': True,
                        'mode': 'local' if firestore_service.use_local_data else 'cloud'
                    },
                    'gemini': {
                        'available': gemini_service.is_service_available()
                    },
                    'tts': {
                        'available': tts_service.is_service_available(),
                        'provider': 'gTTS'
                    }
                },
                'timestamp': logger.handlers[0].formatter.formatTime(
                    logging.LogRecord('', 0, '', 0, '', (), None)
                )
            }
            
            return jsonify(health_status), 200
            
        except Exception as e:
            logger.error(f"Erreur lors du health check: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 503
    
    # Gestionnaire d'erreurs pour les requêtes non trouvées (404)
    @app.errorhandler(404)
    def not_found(error):
        """
        Gère les erreurs 404 (Not Found).
        
        Args:
            error: Erreur Flask
            
        Returns:
            JSON: Message d'erreur formaté
        """
        logger.warning(f"404 Not Found: {error}")
        return jsonify({
            'success': False,
            'error': 'Endpoint non trouvé',
            'message': 'L\'endpoint demandé n\'existe pas',
            'available_endpoints': '/',
            'documentation': '/kumajala-api/v1'
        }), 404
    
    # Gestionnaire d'erreurs pour les méthodes non autorisées (405)
    @app.errorhandler(405)
    def method_not_allowed(error):
        """
        Gère les erreurs 405 (Method Not Allowed).
        
        Args:
            error: Erreur Flask
            
        Returns:
            JSON: Message d'erreur formaté
        """
        logger.warning(f"405 Method Not Allowed: {error}")
        return jsonify({
            'success': False,
            'error': 'Méthode non autorisée',
            'message': 'La méthode HTTP utilisée n\'est pas supportée pour cet endpoint'
        }), 405
    
    # Gestionnaire d'erreurs pour les payloads trop larges (413)
    @app.errorhandler(413)
    def request_entity_too_large(error):
        """
        Gère les erreurs 413 (Request Entity Too Large).
        
        Args:
            error: Erreur Flask
            
        Returns:
            JSON: Message d'erreur formaté
        """
        logger.warning(f"413 Payload Too Large: {error}")
        return jsonify({
            'success': False,
            'error': 'Contenu trop volumineux',
            'message': 'La taille de la requête dépasse la limite autorisée (16MB)'
        }), 413
    
    # Gestionnaire d'erreurs pour les erreurs internes du serveur (500)
    @app.errorhandler(500)
    def internal_error(error):
        """
        Gère les erreurs 500 (Internal Server Error).
        
        Args:
            error: Erreur Flask
            
        Returns:
            JSON: Message d'erreur formaté
        """
        logger.error(f"500 Internal Server Error: {error}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Erreur interne du serveur',
            'message': 'Une erreur inattendue s\'est produite'
        }), 500
    
    # Middleware pour logger toutes les requêtes
    @app.before_request
    def log_request_info():
        """
        Log les informations de chaque requête entrante.
        """
        from flask import request
        logger.info(f"➡️  {request.method} {request.path} - IP: {request.remote_addr}")
    
    # Middleware pour logger toutes les réponses
    @app.after_request
    def log_response_info(response):
        """
        Log les informations de chaque réponse sortante.
        
        Args:
            response: Objet Response Flask
            
        Returns:
            Response: La réponse non modifiée
        """
        from flask import request
        logger.info(
            f"⬅️  {request.method} {request.path} - "
            f"Status: {response.status_code} - "
            f"Size: {response.content_length or 0} bytes"
        )
        return response
    
    logger.info("✅ Application Flask configurée avec succès")
    
    return app


if __name__ == '__main__':
    # Création de l'application Flask
    app = create_app()
    
    # Configuration du serveur
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    
    logger.info(f"🚀 Démarrage du serveur sur {host}:{port}")
    logger.info(f"📱 Frontend URL: http://localhost:5173")
    logger.info(f"🔌 API Base URL: http://localhost:{port}/kumajala-api/v1")
    
    # Lancement du serveur Flask
    try:
        app.run(
            host=host,
            port=port,
            debug=debug,
            use_reloader=debug,  # Auto-reload en mode debug
            threaded=True  # Support de requêtes concurrentes
        )
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt du serveur (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Erreur lors du démarrage du serveur: {e}", exc_info=True)
        raise