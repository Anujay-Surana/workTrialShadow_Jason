const API_BASE_URL = 'http://localhost:8080';

// Check authentication status on page load
async function checkAuthStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/status`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.authenticated && data.user) {
            showAuthenticatedUI(data.user);
        } else {
            showSignInUI();
        }
    } catch (error) {
        console.error('Error checking auth status:', error);
        showSignInUI();
    }
}

// Show sign-in UI
function showSignInUI() {
    document.getElementById('signInSection').classList.remove('hidden');
    document.getElementById('searchSection').classList.add('hidden');
    document.getElementById('userInfo').classList.add('hidden');
}

// Show authenticated UI
function showAuthenticatedUI(user) {
    document.getElementById('signInSection').classList.add('hidden');
    document.getElementById('searchSection').classList.remove('hidden');
    document.getElementById('userInfo').classList.remove('hidden');
    
    // Set user info
    document.getElementById('userName').textContent = user.name || 'User';
    document.getElementById('userEmail').textContent = user.email || '';
}

// Handle Google Sign-In button click
function handleGoogleSignIn() {
    window.location.href = `${API_BASE_URL}/auth/google`;
}

// Handle Sign Out button click
async function handleSignOut() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            // Show sign-in UI
            showSignInUI();
        } else {
            console.error('Logout failed');
            // Still show sign-in UI even if logout request failed
            showSignInUI();
        }
    } catch (error) {
        console.error('Error during logout:', error);
        // Still show sign-in UI even if logout request failed
        showSignInUI();
    }
}

// Show success notification
function showSuccessNotification() {
    const modal = document.getElementById('successModal');
    modal.classList.remove('hidden');
    
    // Hide after 3 seconds
    setTimeout(() => {
        modal.classList.add('hidden');
    }, 3000);
}

// Check if redirected from OAuth callback
function checkOAuthCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('auth') === 'success') {
        showSuccessNotification();
        // Clean up URL
        window.history.replaceState({}, document.title, window.location.pathname);
        // Refresh auth status
        checkAuthStatus();
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Set up Google Sign-In button
    document.getElementById('googleSignInBtn').addEventListener('click', handleGoogleSignIn);
    
    // Set up Sign Out button
    document.getElementById('signOutBtn').addEventListener('click', handleSignOut);
    
    // Check OAuth callback
    checkOAuthCallback();
    
    // Check auth status
    checkAuthStatus();
});

