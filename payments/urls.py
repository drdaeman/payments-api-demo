from django.urls import include, path

from rest_framework import routers

from . import views


router = routers.DefaultRouter()
router.register("owners", views.OwnerViewSet)
router.register("accounts", views.AccountViewSet)
router.register("payments", views.PaymentViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
