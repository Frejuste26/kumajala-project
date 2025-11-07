import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

class Config:
    """Configuration de base pour l'application Flask"""
    
    # Configuration Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'kumajala-secret-key-default')
    DEBUG = os.getenv('FLASK_ENV') == 'development'
    
    # Configuration CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')
    
    # Configuration des APIs externes
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    # Configuration de la base de données
    USE_LOCAL_DATA = os.getenv('USE_LOCAL_DATA', 'true').lower() == 'true'
    
    # Configuration de logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Limites de l'API
    MAX_TEXT_LENGTH = int(os.getenv('MAX_TEXT_LENGTH', '1000'))
    MAX_BATCH_SIZE = int(os.getenv('MAX_BATCH_SIZE', '10'))
    
    # Configuration TTS
    TTS_DEFAULT_LANGUAGE = os.getenv('TTS_DEFAULT_LANGUAGE', 'fr')
    
    @staticmethod
    def validate():
        """Valide la configuration et affiche des avertissements si nécessaire"""
        warnings = []
        
        if not Config.GEMINI_API_KEY:
            warnings.append("GEMINI_API_KEY non définie - Service Gemini indisponible")
        
        if not Config.GOOGLE_APPLICATION_CREDENTIALS and not Config.USE_LOCAL_DATA:
            warnings.append("GOOGLE_APPLICATION_CREDENTIALS non définie - Utilisation des données locales")
        
        if Config.SECRET_KEY == 'kumajala-secret-key-default':
            warnings.append("SECRET_KEY par défaut utilisée - Changez-la en production")
        
        return warnings

class DevelopmentConfig(Config):
    """Configuration pour le développement"""
    DEBUG = True
    
class ProductionConfig(Config):
    """Configuration pour la production"""
    DEBUG = False
    
class TestingConfig(Config):
    """Configuration pour les tests"""
    TESTING = True
    USE_LOCAL_DATA = True

# Dictionnaire des configurations
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}