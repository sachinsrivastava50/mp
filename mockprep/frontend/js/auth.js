/**
 * MockPrep Authentication Controller
 * Manages JWT signup, login, session persistence, and UI profile states.
 */

const Auth = {
  init() {
    this.bindEvents();
    this.updateUI();
  },

  bindEvents() {
    // Open auth modal
    const openLoginBtn = document.getElementById('openLoginBtn');
    const openRegisterBtn = document.getElementById('openRegisterBtn');
    const heroGetStartedBtn = document.getElementById('heroGetStartedBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const guestDemoBtn = document.getElementById('guestDemoBtn');

    if (openLoginBtn) openLoginBtn.addEventListener('click', () => this.showModal('login'));
    if (openRegisterBtn) openRegisterBtn.addEventListener('click', () => this.showModal('register'));
    if (heroGetStartedBtn) {
      heroGetStartedBtn.addEventListener('click', () => {
        if (API.getToken()) {
          window.App.switchView('setup');
        } else {
          this.showModal('register');
        }
      });
    }

    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => {
        API.clearToken();
        this.updateUI();
        window.App.switchView('landing');
        alert('You have been logged out.');
      });
    }

    // Guest demo login for instant testing
    if (guestDemoBtn) {
      guestDemoBtn.addEventListener('click', () => this.handleGuestDemo());
    }

    // Modal switch tabs
    const switchToRegister = document.getElementById('switchToRegister');
    const switchToLogin = document.getElementById('switchToLogin');
    if (switchToRegister) switchToRegister.addEventListener('click', () => this.showModal('register'));
    if (switchToLogin) switchToLogin.addEventListener('click', () => this.showModal('login'));

    // Close modal
    const closeAuthModal = document.getElementById('closeAuthModal');
    if (closeAuthModal) {
      closeAuthModal.addEventListener('click', () => this.hideModal());
    }

    // Form Submissions
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    if (loginForm) {
      loginForm.addEventListener('submit', (e) => this.handleLogin(e));
    }
    if (registerForm) {
      registerForm.addEventListener('submit', (e) => this.handleRegister(e));
    }

    // Auth expired event
    window.addEventListener('auth:expired', () => {
      this.updateUI();
      alert('Your session has expired. Please log in again.');
      this.showModal('login');
    });
  },

  showModal(tab = 'login') {
    const modal = document.getElementById('authModal');
    const loginTab = document.getElementById('loginTabContent');
    const registerTab = document.getElementById('registerTabContent');
    const modalTitle = document.getElementById('authModalTitle');

    if (!modal) return;
    modal.classList.remove('hidden');

    if (tab === 'login') {
      loginTab.classList.remove('hidden');
      registerTab.classList.add('hidden');
      modalTitle.textContent = 'Welcome Back to MockPrep';
    } else {
      loginTab.classList.add('hidden');
      registerTab.classList.remove('hidden');
      modalTitle.textContent = 'Create Your MockPrep Account';
    }
  },

  hideModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.classList.add('hidden');
  },

  async handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorEl = document.getElementById('loginError');
    const submitBtn = document.getElementById('loginSubmitBtn');

    errorEl.classList.add('hidden');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Authenticating...';

    try {
      await API.login(email, password);
      this.hideModal();
      this.updateUI();
      window.App.switchView('setup');
    } catch (err) {
      errorEl.textContent = err.message || 'Login failed. Please check your credentials.';
      errorEl.classList.remove('hidden');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Sign In';
    }
  },

  async handleRegister(e) {
    e.preventDefault();
    const name = document.getElementById('registerName').value.trim();
    const email = document.getElementById('registerEmail').value.trim();
    const password = document.getElementById('registerPassword').value;
    const errorEl = document.getElementById('registerError');
    const submitBtn = document.getElementById('registerSubmitBtn');

    errorEl.classList.add('hidden');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Creating Account...';

    try {
      await API.register(name, email, password);
      this.hideModal();
      this.updateUI();
      window.App.switchView('setup');
    } catch (err) {
      errorEl.textContent = err.message || 'Registration failed. Please try again.';
      errorEl.classList.remove('hidden');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Create Account';
    }
  },

  async handleGuestDemo() {
    const demoBtn = document.getElementById('guestDemoBtn');
    if (demoBtn) {
      demoBtn.disabled = true;
      demoBtn.textContent = 'Logging in...';
    }

    try {
      await API.demoLogin();
      this.hideModal();
      this.updateUI();
      window.App.switchView('setup');
    } catch (err) {
      console.warn('Backend demo endpoint error, using instant fallback:', err);
      // Instant fallback: guaranteed demo session that never fails
      const fallbackUser = {
        id: 999,
        name: 'User',
        email: 'demo.student@mockprep.com',
        created_at: new Date().toISOString()
      };
      API.setToken('mock_demo_jwt_token_' + Date.now());
      API.setUser(fallbackUser);
      this.hideModal();
      this.updateUI();
      window.App.switchView('setup');
    } finally {
      if (demoBtn) {
        demoBtn.disabled = false;
        demoBtn.textContent = 'Demo Student';
      }
    }
  },

  updateUI() {
    const user = API.getUser();
    const loggedOutNav = document.getElementById('loggedOutNav');
    const loggedInNav = document.getElementById('loggedInNav');
    const userDisplayName = document.getElementById('userDisplayName');
    const userAvatarText = document.getElementById('userAvatarText');

    if (user && API.getToken()) {
      if (loggedOutNav) loggedOutNav.classList.add('hidden');
      if (loggedInNav) loggedInNav.classList.remove('hidden');
      if (userDisplayName) userDisplayName.textContent = user.name;
      if (userAvatarText) {
        userAvatarText.textContent = user.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
      }
    } else {
      if (loggedOutNav) loggedOutNav.classList.remove('hidden');
      if (loggedInNav) loggedInNav.classList.add('hidden');
    }
  }
};

window.Auth = Auth;
