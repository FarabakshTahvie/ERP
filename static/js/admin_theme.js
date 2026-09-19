(function() {
    // Set default admin theme to Light
    var currentTheme = localStorage.getItem('adminTheme');
    if (!currentTheme || currentTheme === '"dark"' || currentTheme === 'dark') {
        localStorage.setItem('adminTheme', JSON.stringify('light'));
    }
})();
