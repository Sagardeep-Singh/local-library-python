import datetime
import uuid

# Required to grant the permission needed to set a book as returned.
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Author, Book, BookInstance, Genre, Language


class AuthorListViewTest(TestCase):
    '''Class to test the Author list view.'''

    @classmethod
    def setUpTestData(cls):
        '''Setting up 13 authors to test with.'''
        # Create 13 authors for pagination tests
        number_of_authors = 13

        for author_id in range(number_of_authors):
            Author.objects.create(
                first_name=f'Christian {author_id}',
                last_name=f'Surname {author_id}',
            )

    def test_view_url_exists_at_desired_location(self):
        '''Test the list author URL.'''
        response = self.client.get('/catalog/authors/', follow=True)
        self.assertEqual(response.status_code, 200)

    def test_view_url_accessible_by_name(self):
        '''Testing the name of the author list URL.'''
        response = self.client.get(reverse('authors'), follow=True)
        self.assertEqual(response.status_code, 200)

    def test_view_uses_correct_template(self):
        '''Testing the template that is used for the list authors view.'''
        response = self.client.get(reverse('authors'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'catalog/author_list.html')

    def test_pagination_is_ten(self):
        '''Testing that the URL returns 10 authors on a page at most.'''
        response = self.client.get(reverse('authors'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('is_paginated' in response.context)
        self.assertTrue(response.context['is_paginated'])
        self.assertTrue(len(response.context['author_list']) == 10)

    def test_lists_all_authors(self):
        '''Testing that all the authors are returned by this view.'''
        # Get second page and confirm it has (exactly) remaining 3 items
        response = self.client.get(reverse('authors')+'?page=2', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('is_paginated' in response.context)
        self.assertTrue(response.context['is_paginated'])
        self.assertTrue(len(response.context['author_list']) == 3)


class LoanedBookInstancesByUserListViewTest(TestCase):
    '''Class to test the view to display the books loaned to a user.'''

    def setUp(self):
        # Create two users
        test_user1 = User.objects.create_user(
            username='testuser1', password='1X<ISRUkw+tuK')
        test_user2 = User.objects.create_user(
            username='testuser2', password='2HJ1vRV0Z&3iD')

        test_user1.save()
        test_user2.save()

        # Create a book
        test_author = Author.objects.create(
            first_name='John', last_name='Smith')
        Genre.objects.create(name='Fantasy')
        test_language = Language.objects.create(name='English')
        test_book = Book.objects.create(
            title='Book Title',
            summary='My book summary',
            isbn='ABCDEFG',
            author=test_author,
            language=test_language,
        )

        # Create genre as a post-step
        genre_objects_for_book = Genre.objects.all()
        # Direct assignment of many-to-many types not allowed.
        test_book.genre.set(genre_objects_for_book)
        test_book.save()

        # Create 30 BookInstance objects
        number_of_book_copies = 30
        for book_copy in range(number_of_book_copies):
            return_date = timezone.localtime() + datetime.timedelta(days=book_copy % 5)
            the_borrower = test_user1 if book_copy % 2 else test_user2
            status = 'm'
            BookInstance.objects.create(
                book=test_book,
                imprint='Unlikely Imprint, 2016',
                due_back=return_date,
                borrower=the_borrower,
                status=status,
            )

    def test_redirect_if_not_logged_in(self):
        '''Testing that the user is redirected to correct URL if the User is not logged in'''
        response = self.client.get(reverse('my-borrowed'))
        self.assertRedirects(
            response, '/accounts/login/?next=/catalog/mybooks/')

    def test_logged_in_uses_correct_template(self):
        '''Testing that the view uses the correct template if the user is logged in'''
        self.client.login(
            username='testuser1', password='1X<ISRUkw+tuK')
        response = self.client.get(reverse('my-borrowed'))

        # Check our user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        # Check that we got a response "success"
        self.assertEqual(response.status_code, 200)

        # Check we used correct template
        self.assertTemplateUsed(
            response, 'catalog/bookinstance_list_borrowed_user.html')

    def test_only_borrowed_books_in_list(self):
        '''Testing that online the books borrowed by the logged in user are returned'''
        self.client.login(
            username='testuser1', password='1X<ISRUkw+tuK')
        response = self.client.get(reverse('my-borrowed'))

        # Check our user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        # Check that we got a response "success"
        self.assertEqual(response.status_code, 200)

        # Check that initially we don't have any books in list (none on loan)
        self.assertTrue('bookinstance_list' in response.context)
        self.assertEqual(len(response.context['bookinstance_list']), 0)

        # Now change all books to be on loan
        books = BookInstance.objects.all()[:10]

        for book in books:
            book.status = 'o'
            book.save()

        # Check that now we have borrowed books in the list
        response = self.client.get(reverse('my-borrowed'))
        # Check our user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        # Check that we got a response "success"
        self.assertEqual(response.status_code, 200)

        self.assertTrue('bookinstance_list' in response.context)

        # Confirm all books belong to testuser1 and are on loan
        for bookitem in response.context['bookinstance_list']:
            self.assertEqual(response.context['user'], bookitem.borrower)
            self.assertEqual('o', bookitem.status)

    def test_pages_ordered_by_due_date(self):
        '''Testing that the books are ordered by the due date'''
        # Change all books to be on loan
        for book in BookInstance.objects.all():
            book.status = 'o'
            book.save()

        self.client.login(
            username='testuser1', password='1X<ISRUkw+tuK')
        response = self.client.get(reverse('my-borrowed'))

        # Check our user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        # Check that we got a response "success"
        self.assertEqual(response.status_code, 200)

        # Confirm that of the items, only 10 are displayed due to pagination.
        self.assertEqual(len(response.context['bookinstance_list']), 10)

        last_date = 0
        for book in response.context['bookinstance_list']:
            if last_date == 0:
                last_date = book.due_back
            else:
                self.assertTrue(last_date <= book.due_back)
                last_date = book.due_back


class RenewBookInstancesViewTest(TestCase):
    '''Class to test the view to renew a books instance'''

    def setUp(self):
        '''Setting up the users, books and book instances to test this view.'''
        # Create a user
        test_user1 = User.objects.create_user(
            username='testuser1', password='1X<ISRUkw+tuK')
        test_user2 = User.objects.create_user(
            username='testuser2', password='2HJ1vRV0Z&3iD')

        test_user1.save()
        test_user2.save()

        permission = Permission.objects.get(name='Set book as returned')
        test_user2.user_permissions.add(permission)
        test_user2.save()

        # Create a book
        test_author = Author.objects.create(
            first_name='John', last_name='Smith')
        Genre.objects.create(name='Fantasy')
        test_language = Language.objects.create(name='English')
        test_book = Book.objects.create(
            title='Book Title',
            summary='My book summary',
            isbn='ABCDEFG',
            author=test_author,
            language=test_language,
        )

        # Create genre as a post-step
        genre_objects_for_book = Genre.objects.all()
        # Direct assignment of many-to-many types not allowed.
        test_book.genre.set(genre_objects_for_book)
        test_book.save()

        # Create a BookInstance object for test_user1
        return_date = datetime.date.today() + datetime.timedelta(days=5)
        self.test_bookinstance1 = BookInstance.objects.create(
            book=test_book,
            imprint='Unlikely Imprint, 2016',
            due_back=return_date,
            borrower=test_user1,
            status='o',
        )

        # Create a BookInstance object for test_user2
        return_date = datetime.date.today() + datetime.timedelta(days=5)
        self.test_bookinstance2 = BookInstance.objects.create(
            book=test_book,
            imprint='Unlikely Imprint, 2016',
            due_back=return_date,
            borrower=test_user2,
            status='o',
        )

    def test_redirect_if_not_logged_in(self):
        '''Checking that the user is redrected to a login page if not logged in.'''
        response = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}))
        # Manually check redirect (Can't use assertRedirect, because the redirect URL is unpredictable)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_redirect_if_logged_in_but_not_correct_permission(self):
        '''Testing that forbidden response code is returned if the user doesn't have permission to renew a book instance'''
        self.client.login(
            username='testuser1', password='1X<ISRUkw+tuK')
        response = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}), follow=True)
        self.assertEqual(response.status_code, 200)

    def test_logged_in_with_permission_borrowed_book(self):
        '''Testing the renew book view for a book assigned to the current user.'''
        self.client.login(
            username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance2.pk}), follow=True)

        # Check that it lets us login - this is our book and we have the right permissions.
        self.assertEqual(response.status_code, 200)

    def test_logged_in_with_permission_another_users_borrowed_book(self):
        '''Testing the renew book view for a book assigned to a different user.'''
        self.client.login(
            username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}), follow=True)

        # Check that it lets us login. We're a librarian, so we can view any users book
        self.assertEqual(response.status_code, 200)

    def test_http404_for_invalid_book_if_logged_in(self):
        '''Testing that the user gets a 404 response if the book instance doesn't exist'''
        # unlikely UID to match our bookinstance!
        test_uid = uuid.uuid4()
        self.client.login(
            username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': test_uid}), follow=True)
        self.assertEqual(response.status_code, 404)

    def test_uses_correct_template(self):
        '''Testing that correct template is used to renew a book instance.'''
        self.client.login(
            username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}), follow=True)
        self.assertEqual(response.status_code, 200)

        # Check we used correct template
        self.assertTemplateUsed(response, 'catalog/book_renew_librarian.html')

    def test_form_renewal_date_initially_has_date_three_weeks_in_future(self):
        '''Testing that the initial value is the form is set to 3 weeks from today'''
        self.client.login(
            username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}), follow=True)
        self.assertEqual(response.status_code, 200)

        date_3_weeks_in_future = datetime.date.today() + datetime.timedelta(weeks=3)
        self.assertEqual(
            response.context['form'].initial['due_back'], date_3_weeks_in_future)

    def test_redirects_to_all_borrowed_book_list_on_success(self):
        self.client.login(
            username='testuser2', password='2HJ1vRV0Z&3iD')
        valid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=2)
        response = self.client.post(reverse('renew-book-librarian', kwargs={
                                    'pk': self.test_bookinstance1.pk, }), {'due_back': valid_date_in_future}, follow=True)
        self.assertRedirects(response, reverse('all-borrowed'))

    def test_form_invalid_renewal_date_past(self):
        self.client.login(username='testuser2', password='2HJ1vRV0Z&3iD')
        date_in_past = datetime.date.today() - datetime.timedelta(weeks=1)
        response = self.client.post(reverse(
            'renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}), {'due_back': date_in_past})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'due_back',
                             'Invalid date - renewal in past')

    def test_form_invalid_renewal_date_future(self):
        self.client.login(username='testuser2', password='2HJ1vRV0Z&3iD')
        invalid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=5)
        response = self.client.post(reverse('renew-book-librarian', kwargs={
                                    'pk': self.test_bookinstance1.pk}), {'due_back': invalid_date_in_future})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'due_back',
                             'Invalid date - renewal more than 4 weeks ahead')


class AuthorCreateViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a user
        test_user1 = User.objects.create_user(
            username='testuser1', password='1X<ISRUkw+tuK')
        test_user2 = User.objects.create_user(
            username='testuser2', password='2HJ1vRV0Z&3iD')
        test_user1.save()
        test_user2.save()
        permission = Permission.objects.get(name='Set book as returned')
        test_user2.user_permissions.add(permission)
        test_user2.save()

    def test_redirect_if_not_logged_in(self):
        '''Checking that the user is redirected to a login page if not logged in.'''
        response = self.client.get(reverse('author_create'))
        self.assertRedirects(
            response, '/accounts/login/?next=/catalog/author/create/')

    def test_redirect_if_logged_in_but_not_correct_permission(self):
        '''Testing that forbidden response code is returned if the user doesn't have permission to renew a book instance'''
        self.client.login(username='testuser1', password='1X<ISRUkw+tuK')
        response = self.client.get(reverse('author_create'))
        self.assertEqual(response.status_code, 403)

    def test_logged_in_with_permission(self):
        '''Testing the renew book view for a book assigned to the current user.'''
        self.client.login(
            username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(reverse('author_create'))
        # Check that it lets us login - this is our book and we have the right permissions.
        self.assertEqual(response.status_code, 200)

    def test_redirect_if_successfully_created_author(self):
        self.client.login(
            username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.post(reverse('author_create'), {
            'first_name': 'Test',
            'last_name': 'User',
            'date_of_birth': '2000-06-01',
            'date_of_death': ''
        })
        author = Author.objects.first()
        self.assertEqual(response.status_code,302)
        self.assertRedirects(response,author.get_absolute_url())

    def test_uses_correct_template(self):
        '''Testing that correct template is used to renew a book instance.'''
        self.client.login(
            username='testuser2', password='2HJ1vRV0Z&3iD')
        response = self.client.get(reverse('author_create'), follow=True)
        self.assertEqual(response.status_code, 200)

        # Check we used correct template
        self.assertTemplateUsed(response, 'catalog/author_form.html')
