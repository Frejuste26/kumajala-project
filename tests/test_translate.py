import unittest
import json
from app import create_app

class TranslateTestCase(unittest.TestCase):
    """Tests pour les endpoints de traduction"""
    
    def setUp(self):
        """Configuration avant chaque test"""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
    def test_translate_success(self):
        """Test de traduction réussie"""
        response = self.client.post('/kumajala-api/v1/translate', 
            data=json.dumps({
                'text': 'bonjour',
                'targetLanguage': 'bété'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('translation', data)
        
    def test_translate_missing_text(self):
        """Test avec texte manquant"""
        response = self.client.post('/kumajala-api/v1/translate',
            data=json.dumps({
                'targetLanguage': 'bété'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        
    def test_translate_unsupported_language(self):
        """Test avec langue non supportée"""
        response = self.client.post('/kumajala-api/v1/translate',
            data=json.dumps({
                'text': 'bonjour',
                'targetLanguage': 'klingon'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])

if __name__ == '__main__':
    unittest.main()