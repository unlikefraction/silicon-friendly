// Splash screen: ASCII art of 'SF' rendered via canvas sampling
(function() {
    var splash = document.getElementById('splash-screen');
    var asciiEl = document.getElementById('splash-ascii');
    if (!splash || !asciiEl) return;

    // Check if splash was already shown this session
    if (sessionStorage.getItem('sf-splash-shown')) {
        splash.style.display = 'none';
        return;
    }

    var COLS = 80;
    var CHAR_SET = ' .:-=+*#%@';

    function renderASCII() {
        var canvas = document.createElement('canvas');
        var ctx = canvas.getContext('2d');

        // Render "SF" text to canvas
        var fontSize = 120;
        canvas.width = 400;
        canvas.height = 160;

        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#fff';
        ctx.font = '900 ' + fontSize + 'px Inter, Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('SF', canvas.width / 2, canvas.height / 2 + 5);

        // Sample pixels
        var imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        var pixels = imageData.data;
        var aspectRatio = canvas.height / canvas.width;
        var charAspect = 0.55; // mono chars are taller than wide
        var rows = Math.floor(COLS * aspectRatio * charAspect);

        var lines = [];
        for (var y = 0; y < rows; y++) {
            var line = '';
            for (var x = 0; x < COLS; x++) {
                var px = Math.floor((x / COLS) * canvas.width);
                var py = Math.floor((y / rows) * canvas.height);
                var idx = (py * canvas.width + px) * 4;
                var brightness = (pixels[idx] + pixels[idx + 1] + pixels[idx + 2]) / 3;
                var charIdx = Math.floor((brightness / 255) * (CHAR_SET.length - 1));
                line += CHAR_SET[charIdx];
            }
            lines.push(line);
        }

        // Trim empty top/bottom lines
        while (lines.length && lines[0].trim() === '') lines.shift();
        while (lines.length && lines[lines.length - 1].trim() === '') lines.pop();

        asciiEl.textContent = lines.join('\n');
    }

    // Wait for Inter font to load, then render
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(renderASCII);
    } else {
        setTimeout(renderASCII, 200);
    }

    function dismissSplash() {
        splash.classList.add('hidden');
        sessionStorage.setItem('sf-splash-shown', '1');
        setTimeout(function() {
            splash.style.display = 'none';
        }, 800);
    }

    // Dismiss on click
    splash.addEventListener('click', dismissSplash);

    // Auto-dismiss after 3 seconds
    setTimeout(dismissSplash, 3000);
})();
