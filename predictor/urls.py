
from django.urls import path
from . import views
from .views import subscribe, create_checkout_session

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_page, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('house_details/', views.house_details, name='house_details'),
    path('free_user_profile/', views.free_user_profile, name='free_user_profile'),
    path('user_profile_with_subscription/', views.user_profile_with_subscription, name='user_profile_with_subscription'),
    path('subscribe/', views.subscribe, name='subscribe'),
    path('subscription_success/', views.subscription_success, name='subscription_success'),
    path('subscription_cancel/', views.subscription_cancel, name='subscription_cancel'),
    path('create-checkout-session/', create_checkout_session, name='create_checkout_session'),
    path('stripe-webhook/', views.stripe_webhook, name='stripe_webhook'),
   
]