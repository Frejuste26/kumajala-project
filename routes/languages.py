import logging
from flask import Blueprint, jsonify, request
from services.firestore import FirestoreService

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Blueprint principal pour les langues
languages_bp = Blueprint('languages', __name__)

# Service Firestore (ou local)
firestore_service = FirestoreService()


@languages_bp.route('/languages', methods=['GET'])
def list_languages():
    """
    Retourne la liste des langues supportées avec métadonnées.
    """
    try:
        languages = firestore_service.get_supported_languages()
        return jsonify({
            'success': True,
            'languages': languages,
            'totalLanguages': len(languages)
        }), 200
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des langues: {e}")
        return jsonify({'success': False, 'error': 'Erreur interne du serveur'}), 500


@languages_bp.route('/languages/<code>', methods=['GET'])
def get_language_details(code: str):
    """
    Retourne les détails d'une langue par son code.
    """
    try:
        code = code.strip().lower()
        languages = firestore_service.get_supported_languages()
        info = next((l for l in languages if l.get('code') == code), None)
        if not info:
            return jsonify({'success': False, 'error': f"Langue '{code}' non trouvée"}), 404
        return jsonify({'success': True, 'language': info}), 200
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des détails de langue: {e}")
        return jsonify({'success': False, 'error': 'Erreur interne du serveur'}), 500


@languages_bp.route('/languages/<code>/translations', methods=['GET'])
def get_language_translations(code: str):
    """
    Retourne toutes les traductions disponibles pour une langue cible donnée
    (source = français) à partir du stockage courant (local ou Firestore).
    """
    try:
        code = code.strip().lower()
        # Vérifier que la langue est supportée
        supported_codes = [l['code'] for l in firestore_service.get_supported_languages()]
        if code not in supported_codes:
            return jsonify({'success': False, 'error': f"Langue '{code}' non supportée"}), 400

        results = []
        if firestore_service.use_local_data:
            french_map = firestore_service.local_translations.get('fr', {})
            for fr_text, langs in french_map.items():
                if isinstance(langs, dict) and code in langs:
                    results.append({
                        'frenchText': fr_text,
                        'targetLanguage': code,
                        'translation': langs[code]
                    })
        else:
            # Implémentation Firestore complète non fournie (index conseillés)
            logger.warning("Récupération exhaustive Firestore non implémentée")

        return jsonify({
            'success': True,
            'targetLanguage': code,
            'translations': results,
            'total': len(results)
        }), 200
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des traductions pour {code}: {e}")
        return jsonify({'success': False, 'error': 'Erreur interne du serveur'}), 500


@languages_bp.route('/languages/cache/stats', methods=['GET'])
def translations_cache_stats():
    """
    Retourne les statistiques du cache de traductions (côté FirestoreService).
    """
    try:
        stats = firestore_service.get_cache_stats()
        return jsonify({'success': True, 'cache': stats}), 200
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats de cache: {e}")
        return jsonify({'success': False, 'error': 'Erreur interne du serveur'}), 500


@languages_bp.route('/languages/cache/clear', methods=['POST'])
def translations_cache_clear():
    """
    Vide le cache de traductions en mémoire.
    """
    try:
        firestore_service.clear_cache()
        return jsonify({'success': True, 'message': 'Cache vidé avec succès'}), 200
    except Exception as e:
        logger.error(f"Erreur lors du vidage du cache: {e}")
        return jsonify({'success': False, 'error': 'Erreur interne du serveur'}), 500