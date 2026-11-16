"""
Tests for managing posts on the Portfolio page: choosing which posts show on
the public profile, and deleting posts (with their images on Cloudinary).
"""
from unittest import mock

from django.test import TestCase

from core.factories import make_master
from portfolio.models import PortfolioItem
from portfolio.views import _cloudinary_ref

CDN = 'https://res.cloudinary.com/demo/image/upload/v1731700000'


def make_post(master, service='Skin fade', **fields):
    defaults = {'image': f'{CDN}/stylebook/uploads/20261115_{service[:4]}.jpg',
                'generated_image': f'{CDN}/stylebook/generated/placid_{service[:4]}.png'}
    defaults.update(fields)
    return PortfolioItem.objects.create(user=master.user, service=service, **defaults)


class PostTestCase(TestCase):
    def setUp(self):
        self.ana = make_master('ana')
        self.post = make_post(self.ana)
        self.client.force_login(self.ana.user)


class VisibilityTests(PostTestCase):
    def test_new_posts_show_on_the_profile_by_default(self):
        self.assertTrue(self.post.show_on_profile)

    def test_switch_hides_and_shows_a_post(self):
        url = f'/portfolio/{self.post.pk}/visibility/'
        ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        self.assertEqual(self.client.post(url, **ajax).json(), {'show_on_profile': False})
        self.assertEqual(self.client.post(url, **ajax).json(), {'show_on_profile': True})

    def test_switch_without_javascript_reloads_the_portfolio_page(self):
        response = self.client.post(f'/portfolio/{self.post.pk}/visibility/')
        self.assertRedirects(response, '/portfolio/', fetch_redirect_response=False)
        self.post.refresh_from_db()
        self.assertFalse(self.post.show_on_profile)

    def test_public_profile_shows_only_the_chosen_posts(self):
        hidden = make_post(self.ana, 'Beard trim', show_on_profile=False)
        context = self.client.get('/profile/ana/').context
        self.assertEqual(list(context['portfolio_items']), [self.post])
        self.assertEqual(context['portfolio_count'], 1)
        self.assertNotIn(hidden, context['portfolio_items'])

    def test_portfolio_page_lists_every_post_with_its_state(self):
        make_post(self.ana, 'Beard trim', show_on_profile=False)
        response = self.client.get('/portfolio/')
        self.assertEqual(len(response.context['portfolio_items']), 2)
        self.assertEqual(response.context['visible_count'], 1)
        self.assertContains(response, 'aria-checked="false"')
        self.assertContains(response, 'aria-checked="true"')


class DeleteTests(PostTestCase):
    def delete(self, post=None, **extra):
        with mock.patch('cloudinary.uploader.destroy') as destroy:
            response = self.client.post(f'/portfolio/{(post or self.post).pk}/delete/', **extra)
        return response, destroy

    def test_delete_removes_the_post_and_both_images_from_cloudinary(self):
        response, destroy = self.delete()
        self.assertRedirects(response, '/portfolio/', fetch_redirect_response=False)
        self.assertFalse(PortfolioItem.objects.filter(pk=self.post.pk).exists())
        removed = sorted(call.args[0] for call in destroy.call_args_list)
        self.assertEqual(removed, ['stylebook/generated/placid_Skin', 'stylebook/uploads/20261115_Skin'])

    def test_an_image_another_post_still_uses_is_kept(self):
        make_post(self.ana, 'Other', image=self.post.image)          # shares the original photo
        _, destroy = self.delete()
        removed = [call.args[0] for call in destroy.call_args_list]
        self.assertEqual(removed, ['stylebook/generated/placid_Skin'])

    def test_images_not_on_cloudinary_are_left_alone(self):
        post = make_post(self.ana, 'Local', image='20261115_local.jpg', generated_image='/media/generated/x.png')
        _, destroy = self.delete(post)
        destroy.assert_not_called()
        self.assertFalse(PortfolioItem.objects.filter(pk=post.pk).exists())

    def test_post_is_deleted_even_if_cloudinary_fails(self):
        with mock.patch('cloudinary.uploader.destroy', side_effect=ConnectionError('down')), \
                self.assertLogs('portfolio.views', level='ERROR'):
            self.client.post(f'/portfolio/{self.post.pk}/delete/')
        self.assertFalse(PortfolioItem.objects.filter(pk=self.post.pk).exists())

    def test_ajax_delete_answers_json(self):
        response, _ = self.delete(HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json(), {'deleted': True})


class PermissionTests(PostTestCase):
    def test_cannot_hide_or_delete_someone_elses_post(self):
        bens = make_post(make_master('ben'), 'Bens fade')
        with mock.patch('cloudinary.uploader.destroy') as destroy:
            self.assertEqual(self.client.post(f'/portfolio/{bens.pk}/visibility/').status_code, 404)
            self.assertEqual(self.client.post(f'/portfolio/{bens.pk}/delete/').status_code, 404)
        destroy.assert_not_called()
        bens.refresh_from_db()
        self.assertTrue(bens.show_on_profile)

    def test_both_actions_need_post_and_login(self):
        for url in (f'/portfolio/{self.post.pk}/visibility/', f'/portfolio/{self.post.pk}/delete/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        self.assertTrue(self.client.post(f'/portfolio/{self.post.pk}/delete/')['Location'].startswith('/auth/login/'))
        self.assertTrue(PortfolioItem.objects.filter(pk=self.post.pk).exists())


class CloudinaryRefTests(TestCase):
    def test_reads_the_public_id_from_delivery_urls(self):
        cases = {
            f'{CDN}/stylebook/generated/placid_12.png': ('stylebook/generated/placid_12', 'image'),
            'https://res.cloudinary.com/d/image/upload/c_fill,w_800/v17/stylebook/uploads/a.jpg':
                ('stylebook/uploads/a', 'image'),
            'https://res.cloudinary.com/d/raw/upload/v1/stylebook/certificates/3/cert.pdf':
                ('stylebook/certificates/3/cert.pdf', 'raw'),
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(_cloudinary_ref(url), expected)

    def test_anything_else_is_not_a_cloudinary_image(self):
        for url in ('', None, '/media/generated/a.png', 'https://placid.app/x.png', 'https://evil.example/res.cloudinary.com/x'):
            with self.subTest(url=url):
                self.assertIsNone(_cloudinary_ref(url))
