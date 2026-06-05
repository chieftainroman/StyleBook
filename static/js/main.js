// Tab switcher — reservations page
function switchTab(tabId, btn) {
  document.querySelectorAll('.tab-content').forEach(function(el) {
    el.classList.remove('active');
  });
  document.querySelectorAll('.tab').forEach(function(el) {
    el.classList.remove('active');
  });
  document.getElementById('tab-' + tabId).classList.add('active');
  btn.classList.add('active');
}

// Portfolio filter
function filterPortfolio(category, btn) {
  document.querySelectorAll('.filter-btn').forEach(function(el) {
    el.classList.remove('active');
  });
  btn.classList.add('active');

  document.querySelectorAll('.portfolio-card').forEach(function(card) {
    if (category === 'all') {
      card.style.display = '';
    } else {
      card.style.display = card.dataset.category === category ? '' : 'none';
    }
  });
}

// Profile edit panel
function toggleEditProfile() {
  var panel = document.getElementById('editPanel');
  if (panel) {
    if (panel.style.display === 'none' || panel.style.display === '') {
      panel.style.display = 'block';
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      panel.style.display = 'none';
    }
  }
}

// Copy profile link
function copyProfileLink() {
  var url = window.location.origin + '/profile/' + document.querySelector('.profile-name').textContent.trim();
  navigator.clipboard.writeText(url).then(function() {
    var banner = document.getElementById('linkBanner');
    if (banner) {
      banner.style.display = 'block';
      setTimeout(function() { banner.style.display = 'none'; }, 2500);
    }
  });
}