const API_BASE_URL = 'http://localhost:8080';
let initProgressInterval = null;

// Check authentication status on page load
async function checkAuthStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/auth/status`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.authenticated && data.user) {
            // Check initialization status
            if (data.status === 'pending' || data.status === 'processing') {
                showInitializationUI(data);
                startProgressPolling();
            } else if (data.status === 'active') {
                // Initialization complete, redirect to chat
                window.location.href = '/chat.html';
            } else if (data.status === 'error') {
                showErrorUI('Initialization failed. Please try signing out and signing in again.');
            } else {
                showAuthenticatedUI(data.user);
            }
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
    const initSection = document.getElementById('initializationSection');
    if (initSection) initSection.classList.add('hidden');
    stopProgressPolling();
}

// Show authenticated UI
function showAuthenticatedUI(user) {
    document.getElementById('signInSection').classList.add('hidden');
    document.getElementById('searchSection').classList.remove('hidden');
    document.getElementById('userInfo').classList.remove('hidden');
    const initSection = document.getElementById('initializationSection');
    if (initSection) initSection.classList.add('hidden');
    
    // Set user info
    document.getElementById('userName').textContent = user.name || 'User';
    document.getElementById('userEmail').textContent = user.email || '';
    console.log('User:', user);
    document.getElementById('avatar-img').src = user.picture || 'user.png';
    stopProgressPolling();
}

// Show initialization UI
function showInitializationUI(data) {
    document.getElementById('signInSection').classList.add('hidden');
    document.getElementById('searchSection').classList.add('hidden');
    document.getElementById('userInfo').classList.add('hidden');
    
    const initSection = document.getElementById('initializationSection');
    if (!initSection) {
        createInitializationSection();
    } else {
        initSection.classList.remove('hidden');
    }
    
    updateInitializationProgress(data);
}

// Create initialization section dynamically
function createInitializationSection() {
    const container = document.querySelector('.container');
    const initSection = document.createElement('div');
    initSection.id = 'initializationSection';
    initSection.className = 'initialization-section';
    initSection.innerHTML = `
        <div class="init-card">
            <h2>Initializing Your Data</h2>
            <p class="init-message">Please wait while we fetch your emails, calendar events, and files...</p>
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div class="progress-text" id="progressText">0%</div>
            </div>
            <div class="init-phase" id="initPhase">Starting initialization...</div>
        </div>
    `;
    container.appendChild(initSection);
}

// Update initialization progress
function updateInitializationProgress(data) {
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const initPhase = document.getElementById('initPhase');
    
    if (progressFill && progressText && initPhase) {
        const progress = data.init_progress || 0;
        progressFill.style.width = `${progress}%`;
        progressText.textContent = `${progress}%`;
        
        const phaseMessages = {
            'not_started': 'Preparing to initialize...',
            'starting': 'Starting initialization...',
            'fetching_emails': 'Fetching your emails...',
            'emails_fetched': 'Emails fetched successfully',
            'fetching_schedules': 'Fetching your calendar events...',
            'schedules_fetched': 'Calendar events fetched successfully',
            'fetching_files': 'Fetching your drive files...',
            'files_fetched': 'Files fetched successfully',
            'embedding_emails': 'Processing emails...',
            'emails_embedded': 'Emails processed successfully',
            'embedding_schedules': 'Processing calendar events...',
            'schedules_embedded': 'Calendar events processed successfully',
            'embedding_files': 'Processing files...',
            'files_embedded': 'Files processed successfully',
            'completed': 'Initialization complete! Redirecting...',
            'failed': 'Initialization failed. Please try again.'
        };
        
        initPhase.textContent = phaseMessages[data.init_phase] || 'Processing...';
    }
}

// Start polling for progress updates
function startProgressPolling() {
    if (initProgressInterval) {
        clearInterval(initProgressInterval);
    }
    
    initProgressInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/status`, {
                credentials: 'include'
            });
            const data = await response.json();
            
            if (data.authenticated) {
                if (data.status === 'active') {
                    stopProgressPolling();
                    // Redirect to chat page
                    window.location.href = '/chat.html';
                } else if (data.status === 'error') {
                    stopProgressPolling();
                    showErrorUI('Initialization failed. Please try signing out and signing in again.');
                } else if (data.status === 'pending' || data.status === 'processing') {
                    updateInitializationProgress(data);
                }
            }
        } catch (error) {
            console.error('Error polling progress:', error);
        }
    }, 2000); // Poll every 2 seconds
}

// Stop polling for progress updates
function stopProgressPolling() {
    if (initProgressInterval) {
        clearInterval(initProgressInterval);
        initProgressInterval = null;
    }
}

// Show error UI
function showErrorUI(message) {
    const initSection = document.getElementById('initializationSection');
    if (initSection) {
        initSection.innerHTML = `
            <div class="init-card error">
                <h2>Error</h2>
                <p class="error-message">${message}</p>
                <button onclick="handleSignOut()" class="retry-btn">Sign Out</button>
            </div>
        `;
    }
    stopProgressPolling();
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
