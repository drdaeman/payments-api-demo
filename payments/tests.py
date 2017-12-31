import uuid

from django.urls import reverse

from moneyed import Money, PHP, USD

from rest_framework import status
from rest_framework.test import APITestCase

from . import models


# TODO: Add descriptive error messages in all assertion method calls
class OwnerTests(APITestCase):
    """Tests for the Owner model and its API."""

    def test_str(self):
        """Test that ``__str__`` magic method returns ``Owner.name``."""
        owner = models.Owner(name="alice")
        self.assertEqual(str(owner), owner.name)

    def test_list_owners(self):
        """Test listing owners."""
        url = reverse("owner-list")

        # Try without any owners first
        self.assertFalse(models.Owner.objects.exists())
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.json()["results"]), 0)

        # Create a few accounts
        models.Owner.objects.create(name="alice")
        models.Owner.objects.create(name="bob")

        # Now, test that they're listed
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            # XXX: This could be affected by pagination
            # For simplicity, let us assume that page size is large enough
            len(res.json()["results"]),
            models.Owner.objects.count()
        )

    def test_create_owner(self):
        """Ensure we can create owner, but only if names are unique."""
        url = reverse("owner-list")

        # First, ensure there is no "alice" in the database
        self.assertFalse(models.Owner.objects.filter(name="alice").exists())

        # Send a POST request to create "alice"
        res = self.client.post(url, {"name": "alice"}, format="json")
        # And ensure the 201 response and that she exists afterwards
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.Owner.objects.filter(name="alice").exists())

        # Now, ensure that attempts to re-create "alice" fail
        res = self.client.post(url, {"name": "alice"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # And that we're able to fetch "alice" and it's really her name
        url = reverse("owner-detail", kwargs={"name": "alice"})
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["name"], "alice")

    def test_update_owner(self):
        """Ensure that owners can be renamed."""
        # Send a POST request to create "alice"
        url = reverse("owner-list")
        res = self.client.post(url, {"name": "alice"}, format="json")
        # And ensure the 201 response and that she exists afterwards
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.Owner.objects.filter(name="alice").exists())

        # Now, rename "alice" to "allie"
        url = reverse("owner-detail", kwargs={"name": "alice"})
        res = self.client.patch(url, {"name": "allie"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Make sure there is no "alice" anymore
        self.assertFalse(models.Owner.objects.filter(name="alice").exists())
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # And that "allie" now exists
        self.assertTrue(models.Owner.objects.filter(name="allie").exists())
        url = reverse("owner-detail", kwargs={"name": "allie"})
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["name"], "allie")

    def test_delete_owner(self):
        """Ensure that owners can be renamed."""
        # Send a POST request to create "alice"
        url = reverse("owner-list")
        res = self.client.post(url, {"name": "alice"}, format="json")
        # And ensure the 201 response and that she exists afterwards
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.Owner.objects.filter(name="alice").exists())

        # Create two accounts for "alice", with zero and non-zero balances
        owner = models.Owner.objects.get(name="alice")
        models.Account.objects.create(
            owner=owner, name="alice000", balance=Money(0, USD)
        )
        account = models.Account.objects.create(
            owner=owner, name="alice001", balance=Money(1, USD)
        )

        # Try to delete "alice". It should fail, because "alice001" has money
        url = reverse("owner-detail", kwargs={"name": "alice"})
        res = self.client.delete(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Make sure both accounts still exist and "alice000" is not gone
        self.assertEqual(models.Account.objects.filter(owner=owner).count(), 2)

        # Update "alice001" account to have zero balance
        # No payments, just crude patching - sufficient for this test case.
        account.balance = Money(0, USD)
        account.save()

        # Now, deleting "alice" should be possible
        url = reverse("owner-detail", kwargs={"name": "alice"})
        res = self.client.delete(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        # Make sure there is no "alice" anymore
        self.assertFalse(
            models.Account.objects.filter(owner__name="alice").exists()
        )
        self.assertFalse(models.Owner.objects.filter(name="alice").exists())
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class AccountTests(APITestCase):
    """Tests for the Account model and its API."""

    def test_str(self):
        """Test that ``__str__`` magic method returns ``Account.name``."""
        account = models.Account(name="alice")
        self.assertEqual(str(account), account.name)

    def test_list_accounts(self):
        """Test listing accounts."""
        url = reverse("account-list")

        # Try without any accounts first
        self.assertFalse(models.Account.objects.exists())
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.json()["results"]), 0)

        # Create a few accounts
        alice = models.Owner.objects.create(name="alice")
        models.Account.objects.create(name="alice000", owner=alice)
        models.Account.objects.create(name="alice001", owner=alice)
        bob = models.Owner.objects.create(name="bob")
        models.Account.objects.create(name="bob001", owner=bob)

        # Now, test that they're listed
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            # XXX: This could be affected by pagination
            # For simplicity, let us assume that page size is large enough
            len(res.json()["results"]),
            models.Account.objects.count()
        )

        # Test filtering by owner
        res = self.client.get(url, {"owner": "alice"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.json()["results"]), alice.account_set.count())
        res = self.client.get(url, {"owner": "bob"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.json()["results"]), bob.account_set.count())

    def test_create_account(self):
        """Ensure we can create an account, but only if names are unique."""
        url = reverse("account-list")
        data = {"name": "alice001", "owner": "alice", "currency": "USD"}

        # First, try to create account for non-existent owner "alice"
        self.assertFalse(models.Owner.objects.filter(name="alice").exists())
        res = self.client.post(url, data, format="json")
        # And ensure the 201 response and that she exists afterwards
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Create "alice" and try again
        models.Owner.objects.create(name="alice")
        res = self.client.post(url, data, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.Account.objects.filter(
            name="alice001", owner__name="alice"
        ).exists())

        # And that we're able to fetch "alice001" and it's really correct
        url = reverse("account-detail", kwargs={"name": "alice001"})
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res_data = res.json()
        for k, v in data.items():
            self.assertIn(k, res_data)
            self.assertEqual(res_data[k], v)

    def test_delete_account(self):
        """Ensure that accounts can be deleted iif their balance is zero."""
        # Create user "alice" and two accounts, one with $0, another with $1
        alice, _unused = models.Owner.objects.get_or_create(name="alice")
        models.Account.objects.create(
            name="alice000", owner=alice, balance=Money(0, USD)
        )
        models.Account.objects.create(
            name="alice001", owner=alice, balance=Money(1, USD)
        )

        # Try to delete account with $0 balance and make sure this succeeds.
        res = self.client.delete(
            reverse("account-detail", kwargs={"name": "alice000"})
        )
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            models.Account.objects.filter(name="alice000").exists()
        )

        # Try to delete account with $1 balance and ensure we can't do this.
        res = self.client.delete(
            reverse("account-detail", kwargs={"name": "alice001"})
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            models.Account.objects.filter(name="alice001").exists()
        )


class PaymentTests(APITestCase):
    """Tests for the Payment model and its API."""

    @classmethod
    def setUpTestData(cls):  # noqa: N802
        """Set up three accounts (alice, bob and charlie) for payment tests."""
        alice = models.Owner.objects.create(name="alice")
        bob = models.Owner.objects.create(name="bob")
        charlie = models.Owner.objects.create(name="charlie")
        cls.account_alice = models.Account.objects.create(
            name="alice456", owner=alice, balance=Money(0, USD)
        )
        cls.account_bob = models.Account.objects.create(
            name="bob123", owner=bob, balance=Money(100, USD)
        )
        cls.account_charlie = models.Account.objects.create(
            name="charlie999", owner=charlie, balance=(1000, PHP)
        )

    def test_deposit(self):
        """Test succesfully depositing money."""
        url = reverse("payment-list")
        tuid = str(uuid.uuid4())  # Some safety against concurrent tests

        self.account_alice.refresh_from_db(fields=["balance", "currency"])
        initial_balance = self.account_alice.balance

        uid_tx1 = f"test_deposit/{tuid}/tx1"
        res = self.client.post(url, {
            "to_account": self.account_alice.name,
            "amount": "100.00",
            "currency": "USD",
            "unique_id": uid_tx1
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Fetch the Payment from database and verify its properties
        tx1 = models.Payment.objects.select_related().get(unique_id=uid_tx1)
        self.assertEqual(tx1.amount, Money(100, USD))
        self.assertIsNone(tx1.from_account)
        self.assertEqual(tx1.to_account, self.account_alice)

        # This is safe, because tests are isolated in transactions
        self.assertEqual(tx1.destination_balance_before, initial_balance)

        # Check account balance
        self.account_alice.refresh_from_db(fields=["balance", "currency"])
        self.assertEqual(
            self.account_alice.balance, initial_balance + tx1.amount
        )

        # Test that stringifying the Payment model mentions alice
        self.assertIn(self.account_alice.name, str(tx1))

    def test_deposit_no_uid(self):
        """Test succesfully depositing money (without unique_id)."""
        url = reverse("payment-list")

        self.account_alice.refresh_from_db(fields=["balance", "currency"])
        initial_balance = self.account_alice.balance

        res = self.client.post(url, {
            "to_account": self.account_alice.name,
            "amount": "100.00",
            "currency": "USD",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Make sure response has unique_id
        uid_tx1 = res.json().get("unique_id", None)
        self.assertIsNotNone(uid_tx1)

        # Fetch the Payment from database and verify its properties
        tx1 = models.Payment.objects.select_related().get(unique_id=uid_tx1)
        self.assertEqual(tx1.amount, Money(100, USD))
        self.assertIsNone(tx1.from_account)
        self.assertEqual(tx1.to_account, self.account_alice)

        # This is safe, because tests are isolated in transactions
        self.assertEqual(tx1.destination_balance_before, initial_balance)

        # Check account balance
        self.account_alice.refresh_from_db(fields=["balance", "currency"])
        self.assertEqual(
            self.account_alice.balance, initial_balance + tx1.amount
        )

        # Test that stringifying the Payment model mentions alice
        self.assertIn(self.account_alice.name, str(tx1))

    def test_no_accounts(self):
        """Test that payments without both from and to accounts fail."""
        url = reverse("payment-list")
        tuid = str(uuid.uuid4())  # Some safety against concurrent tests

        uid_tx1 = f"test_no_accounts/{tuid}/tx1"
        res = self.client.post(url, {
            "amount": "3.14",
            "currency": "USD",
            "unique_id": uid_tx1
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Ensure no Payment was created
        self.assertFalse(
            models.Payment.objects.filter(unique_id=uid_tx1).exists()
        )

    def test_currency_match(self):
        """Test matching account and payment currencies."""
        url = reverse("payment-list")
        tuid = str(uuid.uuid4())  # Some safety against concurrent tests

        # Test our test setup ;)
        self.assertNotEqual(
            self.account_bob.currency, self.account_charlie.currency
        )

        # Try various payment combinations that would've involned
        # different currencies one way or another. Make sure they all fail.

        uid_tx1 = f"test_transfer/{tuid}/tx1"
        res = self.client.post(url, {
            "from_account": self.account_bob.name,
            "to_account": self.account_charlie.name,
            "amount": "10.00",
            "currency": "USD",
            "unique_id": uid_tx1
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        uid_tx2 = f"test_transfer/{tuid}/tx2"
        res = self.client.post(url, {
            "from_account": self.account_bob.name,
            "to_account": self.account_charlie.name,
            "amount": "10.00",
            "currency": "PHP",
            "unique_id": uid_tx2
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        uid_tx3 = f"test_transfer/{tuid}/tx3"
        res = self.client.post(url, {
            "from_account": self.account_bob.name,
            "to_account": self.account_charlie.name,
            "amount": "10.00",
            "currency": "XBT",
            "unique_id": uid_tx3
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Confirm than to Payments were created in the database
        for uid_tx in (uid_tx1, uid_tx2, uid_tx3):
            self.assertFalse(
                models.Payment.objects.filter(unique_id=uid_tx).exists()
            )

    def test_no_overdraft(self):
        """Test that no overdraft is possible."""
        url = reverse("payment-list")
        tuid = str(uuid.uuid4())  # Some safety against concurrent tests

        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        initial_balance = self.account_bob.balance

        uid_tx1 = f"test_no_overdraft/{tuid}/tx1"
        res = self.client.post(url, {
            "from_account": self.account_bob.name,
            "amount": str((initial_balance + Money(1000, USD)).amount),
            "currency": "USD",
            "unique_id": uid_tx1
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Ensure no Payment was created
        self.assertFalse(
            models.Payment.objects.filter(unique_id=uid_tx1).exists()
        )

        # Check account balance
        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        self.assertEqual(self.account_bob.balance, initial_balance)

    def test_transfer(self):
        """Test money transfer between two accounts."""
        url = reverse("payment-list")
        tuid = str(uuid.uuid4())  # Some safety against concurrent tests

        self.account_alice.refresh_from_db(fields=["balance", "currency"])
        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        initial_balance_alice = self.account_alice.balance
        initial_balance_bob = self.account_bob.balance

        uid_tx1 = f"test_transfer/{tuid}/tx1"
        res = self.client.post(url, {
            "from_account": self.account_bob.name,
            "to_account": self.account_alice.name,
            "amount": "10.00",
            "currency": "USD",
            "unique_id": uid_tx1
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Fetch the Payment from database and verify its properties
        tx1 = models.Payment.objects.select_related().get(unique_id=uid_tx1)
        self.assertEqual(tx1.amount, Money(10, USD))
        self.assertEqual(tx1.from_account, self.account_bob)
        self.assertEqual(tx1.to_account, self.account_alice)

        # This is safe, because tests are isolated in transactions
        self.assertEqual(tx1.source_balance_before, initial_balance_bob)
        self.assertEqual(tx1.destination_balance_before, initial_balance_alice)

        # Check account balances
        self.account_alice.refresh_from_db(fields=["balance", "currency"])
        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        self.assertEqual(
            self.account_bob.balance, initial_balance_bob - tx1.amount
        )
        self.assertEqual(
            self.account_alice.balance, initial_balance_alice + tx1.amount
        )

        # Test that stringifying the Payment model mentions alice and bob
        self.assertIn(self.account_alice.name, str(tx1))
        self.assertIn(self.account_bob.name, str(tx1))

    def test_withdrawal(self):
        """Test succesfully withdrawing money."""
        url = reverse("payment-list")
        tuid = str(uuid.uuid4())  # Some safety against concurrent tests

        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        initial_balance = self.account_bob.balance

        uid_tx1 = f"test_withdrawal/{tuid}/tx1"
        res = self.client.post(url, {
            "from_account": self.account_bob.name,
            "amount": "10.00",
            "currency": "USD",
            "unique_id": uid_tx1
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Fetch the Payment from database and verify its properties
        tx1 = models.Payment.objects.select_related().get(unique_id=uid_tx1)
        self.assertEqual(tx1.amount, Money(10, USD))
        self.assertEqual(tx1.from_account, self.account_bob)
        self.assertIsNone(tx1.to_account)

        # This is safe, because tests are isolated in transactions
        self.assertEqual(tx1.source_balance_before, initial_balance)

        # Check account balance
        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        self.assertEqual(
            self.account_bob.balance, initial_balance - tx1.amount
        )

        # Test that stringifying the Payment model mentions bob
        self.assertIn(self.account_bob.name, str(tx1))
