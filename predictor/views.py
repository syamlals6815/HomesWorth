from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
import pandas as pd
import joblib
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.views import LogoutView
from .models import FreeUserProfile
from django.http import JsonResponse
from django.conf import settings
from django.urls import reverse
import stripe
import json
from django.views.decorators.csrf import csrf_exempt

# Load model and columns
MODEL_PATH = "predictor/ml_models/trained_model.pkl"
EXPECTED_COLUMNS_PATH = "predictor/ml_models/expected_columns.pkl"
CSV_PATH = "static/csv/house_price_data_cochin2.csv"

model = joblib.load(MODEL_PATH)
expected_columns = joblib.load(EXPECTED_COLUMNS_PATH)
data = pd.read_csv(CSV_PATH)
locations = sorted(data["location"].unique())

# Subscription plans
SUBSCRIPTION_PLANS = {
    '1 Month': {'days': 30, 'price': 5000},
    '3 Months': {'days': 90, 'price': 15000},
    '6 Months': {'days': 180, 'price': 25000},
}

plan_price_map = {plan: details['price'] for plan, details in SUBSCRIPTION_PLANS.items()}

def calculate_expiry_date(plan):
    plan_details = SUBSCRIPTION_PLANS.get(plan)
    return timezone.now() + timedelta(days=plan_details['days']) if plan_details else None



def landing_page(request):
    if request.method == "POST":
        # You can handle form data here if needed
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        message = request.POST.get("message")
        # Process the data as required (e.g., save to the database, send an email, etc.)
        return redirect("landing_page")  # Redirect to avoid resubmission on refresh
    return render(request, "landpage.html")


def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not username or not email or not password:
            messages.error(request, 'All fields are required.')
            return render(request, 'signup.html')

        if FreeUserProfile.objects.filter(user__username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'signup.html')

        if FreeUserProfile.objects.filter(user__email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'signup.html')

        user = User.objects.create_user(username=username, email=email, password=password)
        FreeUserProfile.objects.create(user=user)  # Create a profile
        messages.success(request, 'Account created successfully! Please log in.')
        return redirect('login')

    return render(request, 'signup.html')  

def login_page(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
            user = authenticate(request, username=user.username, password=password)

            if user is not None:
                login(request, user)
                
                # Ensure the user has a FreeUserProfile
                if not hasattr(user, 'free_user_profile'):
                    profile = FreeUserProfile.objects.create(user=user)
                    profile.current_plan = "No Plan"  # Initialize with a default plan
                    profile.save()

                # Redirect based on subscription status
                if user.free_user_profile.subscription_expiry and timezone.now() < user.free_user_profile.subscription_expiry:
                    return redirect('user_profile_with_subscription')
                else:
                    return redirect('free_user_profile')
            else:
                messages.error(request, 'Invalid email or password.')
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email.')

    return render(request, 'login.html')


@login_required
def house_details(request):
    entered_data = {}
    prediction_text = ""
    accuracy_text = ""

    if request.method == "POST":
        location = request.POST.get("location", "")
        area_in_sq_ft = request.POST.get("area_in_sq_ft", 0)
        bedrooms = request.POST.get("bedrooms", 0)
        bathrooms = request.POST.get("bathrooms", 0)
        age_of_home = request.POST.get("age_of_home", 0)
        parking_slot = request.POST.get("parking_slot", 0)

        try:
            area_in_sq_ft = float(area_in_sq_ft)
            bedrooms = int(bedrooms)
            bathrooms = int(bathrooms)
            age_of_home = int(age_of_home)
            parking_slot = int(parking_slot)
        except ValueError:
            messages.error(request, "Please enter valid numeric values.")
            return render(request, "house_details.html", {
                "locations": locations,
                "entered_data": entered_data,
                "prediction": prediction_text,
                "accuracy": accuracy_text,
            })

        entered_data = {
            "location": location,
            "area_in_sq_ft": area_in_sq_ft,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "age_of_home": age_of_home,
            "parking_slot": parking_slot,
        }

        input_data = pd.DataFrame({
            "area_in_sq_ft": [area_in_sq_ft],
            "bedrooms": [bedrooms],
            "bathrooms": [bathrooms],
            "age_of_home": [age_of_home],
            "parking_slot": [parking_slot],
        })

        for loc in locations:
            input_data[f"location_{loc}"] = [1 if loc == location else 0]

        for col in expected_columns:
            if col not in input_data.columns:
                input_data[col] = 0
        input_data = input_data[expected_columns]

        try:
            prediction = model.predict(input_data)[0]
            prediction_text = f"₹{prediction:,.2f}"

            matched_row = data[
                (data["location"] == location) &
                (data["area_in_sq_ft"] == area_in_sq_ft) &
                (data["bedrooms"] == bedrooms) &
                (data["bathrooms"] == bathrooms) &
                (data["age_of_home"] == age_of_home) &
                (data["parking_slot"] == parking_slot)
            ]

            if not matched_row.empty:
                actual_price = matched_row["price"].values[0]
                error = abs(prediction - actual_price) / actual_price
                accuracy = 100 - (error * 100)
                accuracy_text = f"Accuracy: {accuracy:.2f}%"
            else:
                accuracy_text = "Accuracy: Not available (no exact match in data)."
        except Exception:
            prediction_text = "Error predicting price. Please try again."
            accuracy_text = ""

    return render(request, "house_details.html", {
        "locations": locations,
        "entered_data": entered_data,
        "prediction": prediction_text,
        "accuracy": accuracy_text,
    })


@login_required
def free_user_profile(request):
    user = request.user
    profile = user.free_user_profile

    show_popup = False
    popup_title = ""
    popup_message = ""

    # Determine the popup message based on trial count and credits
    if profile.can_use_free_trial():
        show_popup = True
        popup_title = f"Trial {profile.trial_count + 1}"
        popup_message = f"You have {profile.credits} credits left. Click OK to access the form."
    else:
        show_popup = True
        popup_title = "Credits Expired"
        popup_message = (
            "Your credits have expired. Please subscribe to continue accessing the form."
        )

    # Handle POST request for accessing the trial form
    if request.method == "POST" and request.POST.get("access_form"):
        if profile.can_use_free_trial():
            profile.use_free_trial()
            return JsonResponse({
                "status": "success",
                "credits": profile.credits,
                "trial_count": profile.trial_count,
            })
        else:
            return JsonResponse({
                "status": "exceeded_limit",
                "message": "Your credits have expired. Please subscribe."
            })

    return render(request, 'free_user_profile.html', {
        'show_popup': show_popup,
        'popup_title': popup_title,
        'popup_message': popup_message,
        'credits': profile.credits,
        'trial_count': profile.trial_count,
    })


@login_required
def user_profile_with_subscription(request):
    user_profile = request.user.free_user_profile  # Access the profile correctly
    
    # Default subscription status
    subscription_status = "Not Subscribed"
    
    # Check if the user has a valid subscription
    if user_profile.subscription_expiry and timezone.now() < user_profile.subscription_expiry:
        subscription_status = "Subscribed"

    # Default current plan
    current_plan = user_profile.current_plan if user_profile.current_plan else "No Plan"

    # Check subscription expiry and handle fallback for when no expiry is set
    subscription_expiry = user_profile.subscription_expiry if user_profile.subscription_expiry else 'N/A'

    context = {
        'user': request.user,
        'subscription_status': subscription_status,
        'current_plan': current_plan,
        'subscription_expiry': subscription_expiry,
        'credits': user_profile.credits,
    }

    return render(request, 'user_profile_with_subscription.html', context)


@login_required
def subscribe(request):
    user_profile = request.user.free_user_profile

    # Check if the user already has an active subscription
    if user_profile.subscription_expiry and timezone.now() < user_profile.subscription_expiry:
        messages.info(request, "You already have an active subscription!")
        return redirect('user_profile_with_subscription')

    if request.method == 'POST':
        selected_plan = request.POST.get('plan')

        if selected_plan not in SUBSCRIPTION_PLANS:
            messages.error(request, "Invalid plan selected!")
            return redirect('subscribe')

        # Update subscription expiry based on the selected plan
        plan_details = SUBSCRIPTION_PLANS[selected_plan]
        user_profile.subscription_expiry = timezone.now() + timedelta(days=plan_details['days'])
        user_profile.current_plan = selected_plan
        user_profile.subscription_status = "Subscribed"  # Set subscription status
        user_profile.save()

        messages.success(request, f"Subscribed to the {selected_plan} plan successfully!")
        return redirect('user_profile_with_subscription')

    return render(request, 'subscribe.html', {
        'plans': SUBSCRIPTION_PLANS,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    })

@csrf_exempt
def create_checkout_session(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plan = data.get('plan')
            user = request.user

            if plan not in plan_price_map:
                return JsonResponse({'error': 'Invalid plan'}, status=400)

            # Create the checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': plan,
                        },
                        'unit_amount': plan_price_map[plan] * 100,  # Assuming the price is in dollars
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f"{request.build_absolute_uri(reverse('subscription_success'))}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=request.build_absolute_uri(reverse('subscription_cancel')),
                metadata={
                    'user_id': user.id,
                    'plan': plan,
                },
                customer_email=user.email  # Use customer_email instead of customer_details
            )

            return JsonResponse({'sessionId': checkout_session.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


        

@login_required
def subscription_success(request):
    user = request.user
    profile = user.free_user_profile

    # Retrieve session using session ID from Stripe
    session_id = request.GET.get('session_id')
    if not session_id:
        messages.error(request, "Invalid session ID.")
        return redirect('subscribe')

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        plan = session.metadata.get('plan')

        if plan and plan in SUBSCRIPTION_PLANS:
            # Update subscription details in the user's profile
            profile.current_plan = plan
            profile.subscription_expiry = calculate_expiry_date(plan)
            profile.subscription_status = "Subscribed"
            profile.save()

            messages.success(request, f"Successfully subscribed to the {plan} plan!")
        else:
            messages.error(request, "Invalid plan or session data.")
            return redirect('subscribe')

    except stripe.error.StripeError as e:
        messages.error(request, f"Stripe error: {str(e)}")
        return redirect('subscribe')

    return redirect('user_profile_with_subscription')


@login_required
def subscription_cancel(request):
    messages.warning(request, "Your subscription process was canceled.")
    return redirect('subscribe')

# @login_required

# def user_profile_with_subscription(request):
#     # Logic to display subscribed user's profile
#     subscription_status = 'Active' if request.user.profile.subscription_expiry and timezone.now() < request.user.profile.subscription_expiry else 'Inactive'
    
#     context = {
#         'user': request.user,
#         'subscription_status': subscription_status,
#         'credits': request.user.profile.credits,
#         'current_plan': request.user.profile.current_plan,
#     }
#     return render(request, 'user_profile_with_subscription.html', context)
    

class CustomLogoutView(SuccessMessageMixin, LogoutView):
    success_message = "You have been logged out successfully."

def logout_view(request):
    logout(request)
    return redirect('landing_page')

import logging
logger = logging.getLogger(__name__)

@csrf_exempt
def stripe_webhook(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return JsonResponse({'error': 'Invalid payload or signature'}, status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.metadata.get('user_id')

        if user_id:
            user = User.objects.get(id=user_id)
            plan = session.metadata.get('plan')

            if plan in SUBSCRIPTION_PLANS:
                profile = user.free_user_profile
                profile.current_plan = plan
                profile.subscription_expiry = calculate_expiry_date(plan)
                profile.save()

    return JsonResponse({'status': 'success'})

