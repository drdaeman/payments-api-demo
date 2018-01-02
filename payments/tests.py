import uuid
from unittest.mock import patch

from django.urls import reverse

from moneyed import Money, PHP, USD

from rest_framework import status
from rest_framework.test import APITestCase

from . import models, pagination


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

    def test_confirm_method(self):
        """Test Payment.confirm behavior."""
        payment = models.Payment.objects.create(
            from_account=self.account_bob,
            to_account=None,
            amount=Money(1000, USD),
            unique_id=str(uuid.uuid4()),
            confirmed=False
        )

        # Verify that trying to pass mismatching accounts fail
        with self.assertRaises(RuntimeError):
            payment.confirm(commit=False, from_account=self.account_alice)
        with self.assertRaises(RuntimeError):
            payment.confirm(commit=False, to_account=self.account_alice)

        # Verify that trying to confirm fails if there is an overdraft
        with self.assertRaises(ValueError):
            payment.confirm(commit=False)

        # Verify that trying to confirm already confirmed payment fails
        payment.confirmed = True  # Fake confirmation
        with self.assertRaises(ValueError):
            payment.confirm(commit=False)

    def test_deposit(self):
        """Test successfully depositing money."""
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

    def test_overdraft_race(self):
        """
        Test depositing money with a race condition simulation.

        This test tries to simulate a race condition by mocking
        PaymentSerializer.validate method to a no-op.
        """
        # Test immediate payments that would overdraft
        # Even without the validate method they shouldn't be possible.
        validator_fmt = "payments.serializers.{cls}.validate"

        with patch(validator_fmt.format(cls="PaymentSerializer")) as v:
            v.side_effect = lambda x: x
            self.test_no_overdraft()
            self.assertTrue(v.called)

        # Test two-phase protocol with overdraft
        # With a short-circuited validation function it should be possible
        # to create new payment now, but trying to commit must fail
        with patch(validator_fmt.format(cls="PaymentConfirmSerializer")) as v:
            v.side_effect = lambda x: x

            self.account_bob.refresh_from_db(fields=["balance", "currency"])
            initial_balance = self.account_bob.balance

            # Just create the Payment directly
            tx1 = models.Payment.objects.create(
                from_account=self.account_bob,
                to_account=None,
                amount=Money(1000, USD),
                unique_id=str(uuid.uuid4()),
                confirmed=False
            )
            url = reverse("payment-detail", kwargs={"pk": tx1.pk})

            # Try confirming the transaction - it should still fail
            res = self.client.patch(url, {"confirmed": True}, format="json")
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

            # The transaction should be still unconfirmed
            tx1.refresh_from_db()
            self.assertFalse(tx1.confirmed)

            # And account balance shouldn't change
            self.account_bob.refresh_from_db(fields=["balance", "currency"])
            self.assertEqual(self.account_bob.balance, initial_balance)

            self.assertTrue(v.called)

    def test_deposit_no_uid(self):
        """Test depositing money in two steps (without unique_id)."""
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
        res_data = res.json()
        uid_tx1 = res_data.get("unique_id", None)
        self.assertIsNotNone(uid_tx1)
        self.assertIn("url", res_data)

        # Fetch the Payment from database and verify its properties
        tx1 = models.Payment.objects.select_related().get(unique_id=uid_tx1)
        self.assertEqual(tx1.amount, Money(100, USD))
        self.assertIsNone(tx1.from_account)
        self.assertEqual(tx1.to_account, self.account_alice)
        self.assertFalse(tx1.confirmed)

        # Check account balance - it shouldn't have changed yet
        self.account_alice.refresh_from_db(fields=["balance", "currency"])
        self.assertEqual(self.account_alice.balance, initial_balance)

        # Mess with the account's balance to verify destination_balance_before
        self.account_alice.balance = initial_balance + Money(1, USD)
        self.account_alice.save()
        initial_balance = self.account_alice.balance

        url = res_data["url"]

        # Try to PATCH with ``confirmed=False``
        # It should fail - the only accepted value is true
        res = self.client.patch(url, {"confirmed": False}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Now, confirm the transaction by PATCHing with ``confirmed=True``
        res = self.client.patch(url, {"confirmed": True}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Check the payment. It should be confirmed now, but otherwise the same
        tx1.refresh_from_db()
        self.assertEqual(tx1.amount, Money(100, USD))
        self.assertIsNone(tx1.from_account)
        self.assertEqual(tx1.to_account, self.account_alice)
        self.assertTrue(tx1.confirmed)

        # Check that initial balance is captured correctly
        # It should be the value at the time of confirmation, not the creation
        self.assertEqual(tx1.destination_balance_before, initial_balance)

        # Check account balance - it should have changed now
        self.account_alice.refresh_from_db(fields=["balance", "currency"])
        self.assertEqual(
            self.account_alice.balance, initial_balance + tx1.amount
        )

    def test_withdrawal_no_uid(self):
        """Test succesfully withdrawing money."""
        url = reverse("payment-list")

        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        initial_balance = self.account_bob.balance

        res = self.client.post(url, {
            "from_account": self.account_bob.name,
            "amount": "10.00",
            "currency": "USD",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Make sure response has unique_id
        res_data = res.json()
        uid_tx1 = res_data.get("unique_id", None)
        self.assertIsNotNone(uid_tx1)
        self.assertIn("url", res_data)

        # Fetch the Payment from database and verify its properties
        tx1 = models.Payment.objects.select_related().get(unique_id=uid_tx1)
        self.assertEqual(tx1.amount, Money(10, USD))
        self.assertEqual(tx1.from_account, self.account_bob)
        self.assertIsNone(tx1.to_account)
        self.assertFalse(tx1.confirmed)

        # Check account balance - it shouldn't have changed yet
        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        self.assertEqual(self.account_bob.balance, initial_balance)

        # Now, temporarily zero the balance (to test for failure)
        self.account_bob.balance = Money(0, USD)
        self.account_bob.save(update_fields=["balance"])

        # Try confirming the payment - it should fail
        url = res_data["url"]
        res = self.client.patch(url, {"confirmed": True}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Fix the balance back (but to a different value)
        initial_balance = initial_balance + Money(1, USD)
        self.account_bob.balance = initial_balance
        self.account_bob.save(update_fields=["balance"])

        # Confirm the payment
        url = res_data["url"]
        res = self.client.patch(url, {"confirmed": True}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Check the payment. It should be confirmed now, but otherwise the same
        tx1.refresh_from_db()
        self.assertEqual(tx1.amount, Money(10, USD))
        self.assertEqual(tx1.from_account, self.account_bob)
        self.assertIsNone(tx1.to_account)
        self.assertTrue(tx1.confirmed)

        # Check that initial balance is captured correctly
        # It should be the value at the time of confirmation, not the creation
        self.assertEqual(tx1.source_balance_before, initial_balance)

        # Check account balance - it should have changed now
        new_balance = initial_balance - tx1.amount
        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        self.assertEqual(self.account_bob.balance, new_balance)

        # Check that attempts to re-confirm the payment fail now
        url = res_data["url"]
        res = self.client.patch(url, {"confirmed": True}, format="json")
        self.assertEqual(res.status_code, status.HTTP_304_NOT_MODIFIED)

        # Check account balance - it should have not changed
        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        self.assertEqual(self.account_bob.balance, new_balance)

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
        """Test that no overdraft is possible (immediate payment)."""
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

    def test_no_overdraft_2pc(self):
        """Test that no overdraft is possible (2PC variant)."""
        url = reverse("payment-list")

        self.account_bob.refresh_from_db(fields=["balance", "currency"])
        initial_balance = self.account_bob.balance

        # Try the two-step protocol variant (only the first step, of course)
        res = self.client.post(url, {
            "from_account": self.account_bob.name,
            "amount": str((initial_balance + Money(1000, USD)).amount),
            "currency": "USD",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

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

    def test_pagination(self):
        """Tests for the Payment pagination and MonotonicCursorPagination."""
        url = reverse("payment-list") + "?limit=10"
        tuid = str(uuid.uuid4())  # Some safety against concurrent tests

        # Check the payments list and make sure it's empty
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        data = res.json()
        self.assertIn("links", data)
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 0)

        # Since there is no data, there are no PKs to refer to.
        # So, no cursors thus all links are null.
        self.assertIn("this", data["links"])
        self.assertIn("next", data["links"])
        self.assertIn("prev", data["links"])
        self.assertIsNone(data["links"]["this"])
        self.assertIsNone(data["links"]["prev"])
        self.assertIsNone(data["links"]["next"])

        # Check that requests with bad cursor values return HTTP 400
        res = self.client.get(url + "&cursor=BADVALUE", format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        res = self.client.get(url + "&cursor=4pqg77iP", format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        res = self.client.get(url + "&cursor=IT0w", format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Generate a hundred of payments. Their data doesn't really matter.
        for idx in range(0, 100):
            models.Payment.objects.create(
                to_account=self.account_alice,
                amount=Money(1, USD),
                unique_id=f"test_pagination/{tuid}/tx{idx}",
                confirmed=False,
            )

        # Iterate from latest data to older items and collect unique_ids
        prev_url = None
        seen_items = set()
        # Iterate 15 times max, so in case of a bug we won't get stuck
        # With limit=10 and 100 entries, 10 times should be enough
        for idx in range(0, 12):  # pragma: no branch
            res = self.client.get(url, format="json")
            self.assertEqual(res.status_code, status.HTTP_200_OK)

            data = res.json()
            self.assertIn("links", data)
            self.assertIn("results", data)

            self.assertIn("this", data["links"])
            self.assertIn("next", data["links"])
            self.assertIn("prev", data["links"])

            for item in data["results"]:
                seen_items.add(item.get("unique_id"))

            if prev_url is None:
                # On the very first query, remember links.prev
                # We'll use it in later test
                prev_url = data["links"]["prev"]
                self.assertEqual(idx, 0)
                self.assertIsNotNone(prev_url)
            url = data["links"]["next"]  # Note, limit value is retained
            if not url:
                break

        # Check that we saw all the 100 payments we've created
        self.assertEqual(len(seen_items), 100)

        # Generate another 25 payments.
        for idx in range(100, 125):
            models.Payment.objects.create(
                to_account=self.account_alice,
                amount=Money(1, USD),
                unique_id=f"test_pagination/{tuid}/tx{idx}",
                confirmed=False,
            )

        url = prev_url  # Start from first seen "prev" link
        for idx in range(0, 5):  # pragma: no branch
            res = self.client.get(url, format="json")
            self.assertEqual(res.status_code, status.HTTP_200_OK)

            data = res.json()
            self.assertIn("links", data)
            self.assertIn("results", data)

            self.assertIn("this", data["links"])
            self.assertIn("next", data["links"])
            self.assertIn("prev", data["links"])

            for item in data["results"]:
                seen_items.add(item.get("unique_id"))

            url = data["links"]["prev"]
            if len(data["results"]) < 1:
                # Stop when there are no more items
                break

        # Check that we saw all the 125 payments we've created up to now
        self.assertEqual(len(seen_items), 125, sorted(seen_items))

        # Check that retrying results in empty and "prev" link doesn't change
        # Note, persistent "prev" links are not actually in the spec and
        # clients shouldn't assume so. It is an implementation detail
        res = self.client.get(url, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("links", data)
        self.assertIn("results", data)
        self.assertEqual(data["links"]["prev"], url)
        self.assertEqual(len(data["results"]), 0)

        # Check pagination limiting behavior
        with patch("payments.views.PaymentViewSet.pagination_class") as p:
            class LimitedPagination(pagination.MonotonicCursorPagination):
                page_size = 10
                max_page_size = 20
            p.return_value = LimitedPagination()

            # Check that page_size is respected
            url = reverse("payment-list")
            res = self.client.get(url, format="json")
            self.assertEqual(res.status_code, status.HTTP_200_OK)

            data = res.json()
            self.assertIn("links", data)
            self.assertIn("results", data)
            self.assertEqual(len(data["results"]), 10)

            # Check that asking for invalid limit is not respected
            res = self.client.get(url + "?limit=0", format="json")
            self.assertEqual(res.status_code, status.HTTP_200_OK)

            data = res.json()
            self.assertIn("links", data)
            self.assertIn("results", data)
            self.assertEqual(len(data["results"]), 10)

            res = self.client.get(url + "?limit=test", format="json")
            self.assertEqual(res.status_code, status.HTTP_200_OK)

            data = res.json()
            self.assertIn("links", data)
            self.assertIn("results", data)
            self.assertEqual(len(data["results"]), 10)

            # Check that asking for more than max_page_size is not respected
            res = self.client.get(url + "?limit=100", format="json")
            self.assertEqual(res.status_code, status.HTTP_200_OK)

            data = res.json()
            self.assertIn("links", data)
            self.assertIn("results", data)
            self.assertEqual(len(data["results"]), 20)
