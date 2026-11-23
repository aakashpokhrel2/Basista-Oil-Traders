from django.urls import path
from apps.authentication import views

app_name = 'authentication'

urlpatterns = [
    # Auth workflow
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.user_logout_view, name='logout'),
    path('password-change/', views.UserPasswordChangeCustomView.as_view(), name='password_change'),
    path('password-change/done/', views.password_change_done_view, name='password_change_done'),

    # Password reset workflow
    path('password-reset/', views.UserPasswordResetCustomView.as_view(), name='password_reset'),
    path('password-reset/done/', views.UserPasswordResetDoneCustomView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.UserPasswordResetConfirmCustomView.as_view(), name='password_reset_confirm'),
    path('reset/done/', views.UserPasswordResetCompleteCustomView.as_view(), name='password_reset_complete'),

    # User profile
    path('profile/', views.profile_view, name='profile'),

    # User management (Owner / Manager)
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('users/<int:pk>/toggle-status/', views.toggle_user_status_view, name='user_toggle_status'),
]
