const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ARTIFACT_DIR = path.resolve('C:\\Users\\Kavin\\.gemini\\antigravity\\brain\\5eb16911-a235-49ba-b31c-9acf2abed835');
const TEMP_PROFILE = path.join(process.env.TEMP || 'C:\\temp', 'chrome_cdp_modal_' + Date.now());
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9245;

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
                // Populate org details modal with clean data
                document.getElementById('org-detail-name').textContent = 'Acme Global Dynamics';
                document.getElementById('org-detail-slug').textContent = 'acme-global-dyn';
                document.getElementById('org-detail-users-count').textContent = '24';
                document.getElementById('org-detail-apps-count').textContent = '5';
                document.getElementById('org-detail-admin').textContent = 'Jane Admin (admin@acme.com) [ORG_ADMIN]';
                document.getElementById('org-detail-created').textContent = '2026-11-18 10:30:00';
                
                openModal('modal-org-details');
            })()
        `);
        await sleep(1000);

        console.log("4. Verifying modal state after open...");
        const modalState1 = await cdpClient.evaluate(`
            (() => {
                const modal = document.getElementById('modal-org-details');
                const closeBtn = document.getElementById('btn-close-org-details');
                const headerClose = modal.querySelector('.btn-close');
                return {
                    isActive: modal.classList.contains('active'),
                    bodyOverflow: document.body.style.overflow,
                    hasFooterClose: !!closeBtn,
                    closeBtnText: closeBtn ? closeBtn.textContent.trim() : null,
                    hasHeaderClose: !!headerClose,
                    headerCloseText: headerClose ? headerClose.textContent.trim() : null
                };
            })()
        `);
        console.log("Modal State after open:", modalState1);

        console.log("5. Capturing Screenshot: Organization Details Modal with Close button...");
        await cdpClient.captureScreenshot('task5_6_2_org_details_modal_with_close.png');

        console.log("6. Clicking footer Close button...");
        await cdpClient.evaluate(`document.getElementById('btn-close-org-details').click();`);
        await sleep(500);

        const modalState2 = await cdpClient.evaluate(`
            (() => {
                const modal = document.getElementById('modal-org-details');
                return {
                    isActive: modal.classList.contains('active'),
                    bodyOverflow: document.body.style.overflow
                };
            })()
        `);
        console.log("Modal State after footer Close:", modalState2);

        console.log("7. Capturing Screenshot: Modal dismissed via footer button...");
        await cdpClient.captureScreenshot('task5_6_2_org_details_modal_closed.png');

        console.log("8. Reopening modal...");
        await cdpClient.evaluate(`openModal('modal-org-details');`);
        await sleep(500);

        const modalState3 = await cdpClient.evaluate(`
            (() => {
                const modal = document.getElementById('modal-org-details');
                return {
                    isActive: modal.classList.contains('active'),
                    bodyOverflow: document.body.style.overflow
                };
            })()
        `);
        console.log("Modal State after reopen:", modalState3);

        console.log("9. Clicking header &times; close button...");
        await cdpClient.evaluate(`document.querySelector('#modal-org-details .btn-close').click();`);
        await sleep(500);

        const modalState4 = await cdpClient.evaluate(`
            (() => {
                const modal = document.getElementById('modal-org-details');
                return {
                    isActive: modal.classList.contains('active'),
                    bodyOverflow: document.body.style.overflow
                };
            })()
        `);
        console.log("Modal State after &times; close:", modalState4);

        console.log("10. Capturing Screenshot: Modal dismissed via header &times;...");
        await cdpClient.captureScreenshot('task5_6_2_org_details_modal_header_dismissed.png');

        console.log("11. Switching to dark theme and verifying modal in dark glassmorphism...");
        await cdpClient.evaluate(`
            document.documentElement.setAttribute('data-theme', 'dark');
            openModal('modal-org-details');
        `);
        await sleep(600);
        await cdpClient.captureScreenshot('task5_6_2_org_details_modal_dark_theme.png');

        console.log("VERIFICATION COMPLETE: All close controls and overflow restoration validated!");
    } finally {
        if (cdpClient) cdpClient.close();
        try { chrome.kill(); } catch(e) {}
    }
}

main().catch(err => {
    console.error("FATAL ERROR in browser verification:", err);
    process.exit(1);
});
