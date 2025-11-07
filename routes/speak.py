import logging
import time
from flask import Blueprint, request, jsonify
from services.tts import TTSService

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

speak_bp = Blueprint('speak', __name__)

# Initialisation du service TTS
tts_service = TTSService()


@speak_bp.route('/speak', methods=['POST'])
def speak():
    """
    Endpoint pour générer l'audio d'un texte traduit.
    
    Body params:
        text: Texte à synthétiser (requis)
        languageCode: Code de langue pour la synthèse (défaut: 'fr')
        useCache: Utiliser le cache audio (défaut: true)
        
    Returns:
        JSON avec l'audio encodé en base64
    """
    start_time = time.time()

    try:
        # Validation des données d'entrée
        data = request.get_json()

        if not data:
            logger.warning("Requête speak sans données JSON")
            return jsonify({
                'success': False,
                'error': 'Aucune donnée fournie',
                'message': 'Le corps de la requête doit contenir du JSON valide'
            }), 400

        text = data.get('text', '').strip()
        language_code = data.get('languageCode', 'fr').strip().lower()
        use_cache = data.get('useCache', True)

        # Validation du texte
        if not text:
            logger.warning("Requête speak sans texte")
            return jsonify({
                'success': False,
                'error': 'Texte à synthétiser manquant',
                'message': 'Le champ "text" est requis'
            }), 400

        # Limitation de la longueur du texte
        max_length = 5000
        if len(text) > max_length:
            logger.warning(f"Texte trop long pour TTS: {len(text)} caractères")
            return jsonify({
                'success': False,
                'error': f'Le texte est trop long (maximum {max_length} caractères)',
                'textLength': len(text),
                'maxLength': max_length
            }), 400

        # Validation du code de langue (format basique)
        if not language_code or len(language_code) > 10:
            return jsonify({
                'success': False,
                'error': 'Code de langue invalide'
            }), 400

        # Vérification de la disponibilité du service TTS
        if not tts_service.is_service_available():
            logger.error("Service TTS indisponible")
            return jsonify({
                'success': False,
                'error': 'Service de synthèse vocale indisponible',
                'message': 'Le service TTS n\'a pas pu être initialisé'
            }), 503

        # Vérifier si la langue est supportée
        if not tts_service.is_language_supported(language_code):
            supported_langs = tts_service.get_supported_languages()
            
            # Avertissement spécial pour les langues africaines
            african_languages = ['bété', 'baoulé', 'mooré', 'agni']
            if language_code in african_languages:
                logger.warning(
                    f"Langue africaine '{language_code}' non supportée par gTTS. "
                    f"Utilisation du français par défaut."
                )
                # Continuer avec le français comme fallback
                language_code = 'fr'
            else:
                logger.warning(f"Langue non supportée: {language_code}")
                return jsonify({
                    'success': False,
                    'error': f'Langue "{language_code}" non supportée par le service TTS',
                    'supportedLanguages': list(supported_langs.keys())[:20],  # Limiter pour la réponse
                    'totalSupportedLanguages': len(supported_langs)
                }), 400

        logger.info(f"Synthèse TTS: '{text[:50]}...' en '{language_code}'")
        
        # Synthèse vocale via le service TTSService
        result = tts_service.synthesize_speech(text, language_code, use_cache=use_cache)

        if not result or not result.get('success'):
            error_message = result.get('error', 'Erreur inconnue lors de la synthèse vocale.')
            logger.error(f"Échec de la synthèse vocale: {error_message}")
            return jsonify({
                'success': False,
                'error': error_message,
                'text': text[:100],  # Retourner un extrait du texte
                'languageCode': language_code
            }), 500

        # Calcul du temps de traitement
        processing_time = round((time.time() - start_time) * 1000, 2)
        
        logger.info(
            f"Synthèse vocale réussie en {processing_time}ms "
            f"({result.get('audio_size_bytes', 0)} bytes, cached: {result.get('cached', False)})"
        )

        # Réponse de succès
        response_data = {
            'success': True,
            'audioBase64': result['audio_base64'],
            'contentType': result['content_type'],
            'text': text,
            'languageCode': language_code,
            'actualTTSLanguage': result.get('actual_tts_language', language_code),
            'processingTime': f"{processing_time}ms",
            'audioSizeBytes': result.get('audio_size_bytes', 0),
            'cached': result.get('cached', False)
        }
        
        # Avertissement si langue africaine
        if language_code in ['bété', 'baoulé', 'mooré', 'agni']:
            response_data['warning'] = (
                f"La langue '{language_code}' n'est pas supportée par gTTS. "
                "L'audio a été généré en français. "
                "Pour une prononciation authentique, veuillez utiliser un service TTS supportant les langues africaines."
            )

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Erreur inattendue dans /speak: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Erreur interne du serveur',
            'message': 'Une erreur inattendue s\'est produite lors de la synthèse vocale'
        }), 500


@speak_bp.route('/speak/languages', methods=['GET'])
def get_supported_tts_languages():
    """
    Endpoint pour récupérer les langues supportées par le service TTS.
    
    Returns:
        JSON avec la liste des langues supportées par gTTS
    """
    try:
        if not tts_service.is_service_available():
            return jsonify({
                'success': False,
                'error': 'Service TTS indisponible'
            }), 503
        
        supported_languages = tts_service.get_supported_languages()
        
        return jsonify({
            'success': True,
            'supportedLanguages': supported_languages,
            'totalLanguages': len(supported_languages),
            'note': 'gTTS ne supporte pas les langues africaines locales (Bété, Baoulé, Mooré, Agni)'
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des langues TTS: {e}")
        return jsonify({
            'success': False,
            'error': 'Erreur interne du serveur'
        }), 500


@speak_bp.route('/speak/cache/stats', methods=['GET'])
def get_tts_cache_stats():
    """
    Endpoint pour récupérer les statistiques du cache audio.
    
    Returns:
        JSON avec les statistiques du cache
    """
    try:
        stats = tts_service.get_cache_stats()
        
        return jsonify({
            'success': True,
            'cache': stats
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats de cache TTS: {e}")
        return jsonify({
            'success': False,
            'error': 'Erreur interne du serveur'
        }), 500


@speak_bp.route('/speak/cache/clear', methods=['POST'])
def clear_tts_cache():
    """
    Endpoint pour vider le cache audio.
    
    Returns:
        JSON confirmant la suppression du cache
    """
    try:
        tts_service.clear_cache()
        
        logger.info("Cache audio TTS vidé avec succès")
        
        return jsonify({
            'success': True,
            'message': 'Cache audio vidé avec succès'
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur lors du vidage du cache TTS: {e}")
        return jsonify({
            'success': False,
            'error': 'Erreur interne du serveur'
        }), 500


@speak_bp.route('/speak/alternatives', methods=['GET'])
def get_tts_alternatives():
    """
    Endpoint pour obtenir des recommandations d'alternatives TTS
    supportant les langues africaines locales.
    
    Returns:
        JSON avec les alternatives recommandées
    """
    try:
        alternatives = tts_service.get_recommended_alternatives()
        
        return jsonify({
            'success': True,
            'alternatives': alternatives
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des alternatives TTS: {e}")
        return jsonify({
            'success': False,
            'error': 'Erreur interne du serveur'
        }), 500


@speak_bp.route('/speak/check-language', methods=['POST'])
def check_language_support():
    """
    Endpoint pour vérifier si une langue est supportée par le service TTS.
    
    Body params:
        languageCode: Code de langue à vérifier
        
    Returns:
        JSON indiquant si la langue est supportée
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Aucune donnée fournie'
            }), 400
        
        language_code = data.get('languageCode', '').strip().lower()
        
        if not language_code:
            return jsonify({
                'success': False,
                'error': 'Code de langue manquant'
            }), 400
        
        is_supported = tts_service.is_language_supported(language_code)
        
        response_data = {
            'success': True,
            'languageCode': language_code,
            'isSupported': is_supported
        }
        
        # Ajouter des informations supplémentaires si non supportée
        if not is_supported:
            african_languages = ['bété', 'baoulé', 'mooré', 'agni']
            if language_code in african_languages:
                response_data['fallbackLanguage'] = 'fr'
                response_data['warning'] = (
                    f"La langue '{language_code}' n'est pas supportée par gTTS. "
                    "Le français sera utilisé comme langue de synthèse."
                )
            else:
                supported_langs = tts_service.get_supported_languages()
                response_data['supportedLanguages'] = list(supported_langs.keys())[:10]
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de langue TTS: {e}")
        return jsonify({
            'success': False,
            'error': 'Erreur interne du serveur'
        }), 500