from datetime import date
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from .models import InsurancePlan, Patient, Provider, Bill, BillLineItem


class A5Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.plan = InsurancePlan.objects.create(name='Test plan', plan_type='PPO', deductible=100, coinsurance_pct=20, out_of_pocket_max=1000)
        patient = Patient.objects.create(name='Private Patient', netid='private', email='private@example.test', insurance_plan=cls.plan)
        provider = Provider.objects.create(name='Test provider', insurance_plan=cls.plan, network_status='IN')
        cls.bill = Bill.objects.create(reference_number='SECRET-REF', patient=patient, provider=provider, insurance_plan=cls.plan, bill_date=date(2026,1,1))
        cls.staff = get_user_model().objects.create_user('operator', password='Operator-Password-490', is_staff=True)
        cls.member = get_user_model().objects.create_user('member', password='Member-Password-490')

    def private_urls(self):
        from .urls import urlpatterns
        for route in urlpatterns:
            if route.name in {'home', 'public-plan-types'}:
                continue
            kwargs = {'pk': self.bill.pk} if '<int:pk>' in str(route.pattern) else {'name': 'chart1'} if '<str:name>' in str(route.pattern) else {}
            yield reverse('claims:'+route.name, kwargs=kwargs), route

    def test_every_private_route_anonymous(self):
        for url, route in self.private_urls():
            api = str(route.pattern).startswith('api/') or route.name == 'export-bills-json'
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401 if api else 302)
                self.assertEqual(self.client.post(url).status_code, 401 if api else 302)
    def test_home_and_navigation_do_not_leak(self):
        response = self.client.get('/')
        for text in ['Private Patient', 'SECRET-REF', 'All Bills', 'Manage']:
            self.assertNotContains(response, text)
        self.client.force_login(self.member)
        response = self.client.get('/')
        self.assertContains(response, 'All Bills')
        self.assertContains(response, 'Vega-Lite')
        for text in ['Private Patient', 'SECRET-REF', '>Manage</a>']:
            self.assertNotContains(response, text)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get('/'), 'SECRET-REF')
        self.assertContains(self.client.get('/'), '>Manage</a>')

    def test_regular_user_routes_and_record_privacy(self):
        self.client.force_login(self.member)
        for url, route in self.private_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                expected = 403 if route.name == 'bill-manage' else 404 if route.name == 'bill-detail' else 400 if route.name == 'api-procedures' else 200
                self.assertEqual(response.status_code, expected)
                self.assertNotIn(b'SECRET-REF', response.content)
                self.assertNotIn(b'Private Patient', response.content)
        self.assertEqual(self.client.get('/api/bills/').json()['count'], 0)
        self.assertEqual(self.client.get('/api/summary/providers/').json(), [])
        self.assertEqual(self.client.get('/admin/').status_code, 302)
        self.assertEqual(self.client.post('/bills/manage/', {}).status_code, 403)

    def test_explicit_owner_can_read_only_their_records(self):
        self.bill.patient.user = self.member
        self.bill.patient.save(update_fields=['user'])
        other_plan = InsurancePlan.objects.create(name='Other private plan', plan_type='HMO', deductible=0, coinsurance_pct=0, out_of_pocket_max=0)
        other_patient = Patient.objects.create(name='Other Patient', netid='other', email='other@example.test', insurance_plan=other_plan)
        # Even a shared provider must not leak another patient's bills in aggregates.
        other = Bill.objects.create(reference_number='OTHER-SECRET', patient=other_patient, provider=self.bill.provider, insurance_plan=other_plan, bill_date=date(2026,1,2))
        BillLineItem.objects.create(bill=self.bill, line_number=1, description='test procedure', charged_amount=10)
        BillLineItem.objects.create(bill=other, line_number=1, description='test procedure', charged_amount=900)
        self.client.force_login(self.member)
        self.assertContains(self.client.get('/bills/render/'), 'SECRET-REF')
        self.assertEqual(self.client.get(f'/bills/{self.bill.pk}/').status_code, 200)
        self.assertEqual(self.client.get(f'/bills/{other.pk}/').status_code, 404)
        self.assertEqual(self.client.get('/api/bills/').json()['count'], 1)
        summary = self.client.get('/api/summary/providers/').json()[0]
        self.assertEqual(summary['bill_count'], 1)
        self.assertEqual(summary['total_charged'], 10)
        self.assertNotContains(self.client.post('/bills/lookup/', {'email': 'other@example.test'}), 'OTHER-SECRET')
        for url in ['/api/summary/bills/', '/exports/bills.json', '/exports/bills.csv', '/bills/summary/']:
            self.assertNotContains(self.client.get(url), 'OTHER-SECRET')
        with patch('claims.views_external._fetch_hcpcs', return_value=(0, [])):
            response = self.client.get('/api/procedures/?q=test')
            self.assertNotContains(response, 'OTHER-SECRET')
            self.assertEqual(response.json()['claimsense']['total_charged'], 10)

    def test_public_api_database_only_and_allowlist(self):
        url = reverse('claims:public-plan-types')
        response = self.client.get(url)
        self.assertEqual(response.json(), [{'plan_type':'PPO','plan_count':1}])
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response['Access-Control-Allow-Origin'], '*')
        InsurancePlan.objects.create(name='Another', plan_type='PPO', deductible=0, coinsurance_pct=0, out_of_pocket_max=0)
        self.assertEqual(self.client.get(url).json()[0]['plan_count'],2)
        self.assertEqual(self.client.post(url).status_code,405)

    def test_password_signup_login_logout(self):
        response = self.client.post('/accounts/signup/', {'username':'newstudent','email':'student@example.test','password1':'Different-Password-490!','password2':'Different-Password-490!'})
        self.assertEqual(response.status_code,302)
        user = get_user_model().objects.get(username='newstudent')
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password('Different-Password-490!'))
        self.client.post('/accounts/logout/')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.post('/accounts/login/',{'login':'newstudent','password':'incorrect'}).status_code,200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.post('/accounts/login/',{'login':'newstudent','password':'Different-Password-490!'}).status_code,302)
        self.assertIn('_auth_user_id',self.client.session)
        self.assertEqual(self.client.get('/bills/render/').status_code, 200)
        self.assertContains(self.client.get('/'), 'All Bills')
        self.assertEqual(self.client.get('/api/bills/').json()['count'], 0)
        self.client.get('/accounts/logout/')
        self.assertIn('_auth_user_id',self.client.session)
        self.client.post('/accounts/logout/')
        self.assertNotIn('_auth_user_id',self.client.session)

    def test_google_account_uses_regular_user_policy(self):
        from allauth.socialaccount.models import SocialAccount
        user = get_user_model().objects.create_user('google-student')
        SocialAccount.objects.create(user=user, provider='google', uid='test-google-id')
        self.client.force_login(user)
        self.assertFalse(user.is_staff)
        self.assertContains(self.client.get('/'), 'All Bills')
        self.assertEqual(self.client.get('/vega-lite/').status_code, 200)
        self.assertEqual(self.client.get('/api/bills/').json()['count'], 0)
        self.assertEqual(self.client.get('/bills/manage/').status_code, 403)
        # This verifies a signed-in social account, not Google's real callback.

    def test_staff_api_and_bad_filter(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/api/bills/').json()['count'],1)
        self.assertEqual(self.client.get('/api/bills/?since=invalid').status_code,400)
        self.assertEqual(self.client.get('/bills/render/').status_code,200)
        self.assertEqual(self.client.get('/bills/manage/').status_code,200)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        for url in ['/accounts/login/','/accounts/signup/','/accounts/logout/']:
            self.assertEqual(client.post(url,{}).status_code,403)

    def test_unsafe_next_does_not_redirect_external(self):
        response = self.client.post('/accounts/login/?next=https://evil.example/', {'login':'operator','password':'Operator-Password-490'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response['Location'],'/')

    @override_settings(GOOGLE_OAUTH_ENABLED=True, SOCIALACCOUNT_PROVIDERS={'google':{'APPS':[{'client_id':'test-client','secret':'test-only-secret','key':''}]}})
    def test_google_configuration_and_oauth_start(self):
        for url in ['/accounts/login/','/accounts/signup/']:
            self.assertContains(self.client.get(url), 'action="/accounts/google/login/')
        response = self.client.post('/accounts/google/login/')
        self.assertEqual(response.status_code,302)
        self.assertTrue(response['Location'].startswith('https://accounts.google.com/'))
        self.assertIn('http%3A%2F%2Ftestserver%2Faccounts%2Fgoogle%2Flogin%2Fcallback%2F',response['Location'])
        self.assertIn('state=',response['Location'])
        # This tests initiation only, never a real Google authorization/callback.
