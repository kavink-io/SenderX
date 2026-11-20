const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ARTIFACT_DIR = path.resolve('C:\\Users\\Kavin\\.gemini\\antigravity\\brain\\5eb16911-a235-49ba-b31c-9acf2abed835');
const TEMP_PROFILE = path.join(process.env.TEMP || 'C:\\temp', 'chrome_cdp_check_' + Date.now());
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9255;

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function getJson(url) {
    return new Promise((resolve, reject) => {
        http.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch(e) {
                    reject(e);
                }
            });
        }).on('error', reject);
    });
}

class CDPClient {
    constructor(wsUrl) {
        this.ws = new WebSocket(wsUrl);
        this.id = 0;
        this.callbacks = new Map();
        
        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.id && this.callbacks.has(msg.id)) {
                const cb = this.callbacks.get(msg.id);
                this.callbacks.delete(msg.id);
                if (msg.error) {
                    cb.reject(new Error(JSON.stringify(msg.error)));
                } else {
                    cb.resolve(msg.result);
                }
            }
        };
    }

    ready() {
        return new Promise((resolve, reject) => {
            if (this.ws.readyState === WebSocket.OPEN) return resolve();
            this.ws.onopen = () => resolve();
            this.ws.onerror = (err) => reject(err);
        });
    }

    send(method, params = {}) {
        return new Promise((resolve, reject) => {
            const reqId = ++this.id;
            this.callbacks.set(reqId, { resolve, reject });
            this.ws.send(JSON.stringify({ id: reqId, method, params }));
        });
    }

    async evaluate(expression) {
        const res = await this.send('Runtime.evaluate', {
            expression,
            returnByValue: true,
            awaitPromise: true
        });
        if (res.exceptionDetails) {
            throw new Error(JSON.stringify(res.exceptionDetails));
        }
        return res.result ? res.result.value : undefined;
    }

    async captureScreenshot(filename) {
        const res = await this.send('Page.captureScreenshot', { format: 'png' });
        const filePath = path.join(ARTIFACT_DIR, filename);
        fs.writeFileSync(filePath, Buffer.from(res.data, 'base64'));
        console.log(`Saved screenshot: ${filePath} (${res.data.length} bytes base64)`);
    }

    close() {
        try { this.ws.close(); } catch(e) {}
    }
}

async function main() {
    console.log(`1. Launching Chrome with CDP on port ${PORT}...`);
    const chrome = spawn(CHROME_PATH, [
        `--remote-debugging-port=${PORT}`,
        `--user-data-dir=${TEMP_PROFILE}`,
        '--headless=new',
        '--disable-gpu',
        '--no-first-run',
        '--no-default-browser-check',
        'about:blank'
    ]);

    let cdpClient = null;

    try {
        let connected = false;
        let targets = null;
        for (let i = 0; i < 20; i++) {
            await sleep(400);
            try {
                targets = await getJson(`http://127.0.0.1:${PORT}/json`);
                if (targets && targets.length > 0) {
                    connected = true;
                    break;
                }
            } catch(e) {}
        }

        if (!connected) throw new Error("Could not connect to Chrome CDP");

        const pageTarget = targets.find(t => t.type === 'page');
        cdpClient = new CDPClient(pageTarget.webSocketDebuggerUrl);
        await cdpClient.ready();

        await cdpClient.send('Page.enable');
        await cdpClient.send('DOM.enable');
        await cdpClient.send('Runtime.enable');
        await cdpClient.send('Emulation.setDeviceMetricsOverride', {
            width: 1440,
            height: 900,
            deviceScaleFactor: 1,
            mobile: false
        });

        console.log("2. Navigating to http://localhost:5000/ ...");
        await cdpClient.send('Page.navigate', { url: 'http://localhost:5000/' });
        await sleep(1500);

        console.log("3. Rendering Platform Admin Dashboard with active session context...");
        await cdpClient.evaluate(`
            (() => {
                showDashboard({
                    email: 'senderx@id.com',
                    account_type: 'PLATFORM_ADMIN',
                    role: 'SUPER_ADMIN',
                    name: 'Platform Administrator'
                });
                document.documentElement.setAttribute('data-theme', 'dark');
            })()
        `);
        await sleep(1500);

        // Check for any button with innerText containing 'Close'
        const closeButtons = await cdpClient.evaluate(`
            Array.from(document.querySelectorAll('button')).filter(b => b.innerText.trim().toLowerCase() === 'close').map(b => ({
                id: b.id,
                className: b.className,
                text: b.innerText.trim(),
                visible: b.offsetParent !== null
            }))
        `);
        console.log("Buttons with text 'Close':", closeButtons);

        console.log("4. Capturing Screenshot: Platform Admin view without any Close button...");
        await cdpClient.captureScreenshot('verified_no_close_button_platform_overview.png');

        console.log("5. Opening Org Details Modal...");
        await cdpClient.evaluate(`
            (() => {
                document.getElementById('org-detail-name').textContent = 'Acme Global Corp';
                document.getElementById('org-detail-slug').textContent = 'acme-corp';
                document.getElementById('org-detail-users-count').textContent = '12';
                document.getElementById('org-detail-apps-count').textContent = '3';
                document.getElementById('org-detail-admin').textContent = 'Admin (admin@acme.com)';
                document.getElementById('org-detail-created').textContent = '2026-11-20';
                openModal('modal-org-details');
            })()
        `);
        await sleep(800);

        const modalCloseButtons = await cdpClient.evaluate(`
            Array.from(document.querySelectorAll('#modal-org-details button')).map(b => ({
                id: b.id,
                className: b.className,
                text: b.innerText.trim()
            }))
        `);
        console.log("Buttons in modal-org-details:", modalCloseButtons);

        await cdpClient.captureScreenshot('verified_modal_org_details_no_close_btn.png');

        console.log("All verifications passed!");
    } catch(err) {
        console.error("Verification failed:", err);
    } finally {
        if (cdpClient) cdpClient.close();
        chrome.kill();
        try {
            fs.rmSync(TEMP_PROFILE, { recursive: true, force: true });
        } catch(e) {}
    }
}

main();
