// Silicon Friendly - EVM Wallet Payment Flow
// Sends USDC to the configured wallet on the selected chain

const USDC_CONTRACTS = {
    ethereum: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    base: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    polygon: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
    arbitrum: "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    bsc: "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
};

const CHAIN_CONFIG = {
    ethereum: { chainId: "0x1", name: "Ethereum", decimals: 6 },
    base: { chainId: "0x2105", name: "Base", decimals: 6 },
    polygon: { chainId: "0x89", name: "Polygon", decimals: 6 },
    arbitrum: { chainId: "0xa4b1", name: "Arbitrum One", decimals: 6 },
    bsc: { chainId: "0x38", name: "BNB Smart Chain", decimals: 18 },
};

const RECEIVE_WALLET = "0xAfdC6947d877431282F57d9Db843E052F3405f80";
const AMOUNT_USD = 10;

// ERC-20 transfer function signature
const ERC20_TRANSFER_ABI = "0xa9059cbb";

function setStatus(msg, isError = false) {
    const el = document.getElementById("payment-status");
    if (el) {
        el.textContent = msg;
        el.style.color = isError ? "var(--error)" : "var(--accent)";
    }
}

function showPaymentSection(id) {
    document.querySelectorAll(".payment-method-content").forEach(el => el.style.display = "none");
    const target = document.getElementById(id);
    if (target) target.style.display = "block";
}

async function connectWallet() {
    if (!window.ethereum) {
        setStatus("no ethereum wallet detected. install MetaMask or another EVM wallet.", true);
        return null;
    }

    try {
        const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
        if (accounts.length === 0) {
            setStatus("no accounts found. unlock your wallet.", true);
            return null;
        }
        return accounts[0];
    } catch (err) {
        if (err.code === 4001) {
            setStatus("connection rejected by user.", true);
        } else {
            setStatus("wallet connection failed: " + err.message, true);
        }
        return null;
    }
}

async function switchChain(chainKey) {
    const config = CHAIN_CONFIG[chainKey];
    if (!config) return false;

    try {
        await window.ethereum.request({
            method: "wallet_switchEthereumChain",
            params: [{ chainId: config.chainId }],
        });
        return true;
    } catch (err) {
        if (err.code === 4902) {
            setStatus("chain not added to wallet. add " + config.name + " first.", true);
        } else {
            setStatus("failed to switch chain: " + err.message, true);
        }
        return false;
    }
}

function encodeTransferData(to, amount, decimals) {
    // encode ERC-20 transfer(address,uint256)
    const toAddress = to.toLowerCase().replace("0x", "").padStart(64, "0");
    const value = BigInt(amount * (10 ** decimals));
    const valueHex = value.toString(16).padStart(64, "0");
    return ERC20_TRANSFER_ABI + toAddress + valueHex;
}

async function payWithWallet() {
    const chainSelect = document.getElementById("chain-select");
    const chainKey = chainSelect ? chainSelect.value : "base";
    const websiteUrl = document.getElementById("payment-website-url")?.value;

    if (!websiteUrl) {
        setStatus("missing website info.", true);
        return;
    }

    setStatus("connecting wallet...");
    const account = await connectWallet();
    if (!account) return;

    setStatus("switching to " + CHAIN_CONFIG[chainKey].name + "...");
    const switched = await switchChain(chainKey);
    if (!switched) return;

    const contract = USDC_CONTRACTS[chainKey];
    const decimals = CHAIN_CONFIG[chainKey].decimals;
    const data = encodeTransferData(RECEIVE_WALLET, AMOUNT_USD, decimals);

    setStatus("approve the $10 USDC transfer in your wallet...");

    try {
        const txHash = await window.ethereum.request({
            method: "eth_sendTransaction",
            params: [{
                from: account,
                to: contract,
                data: data,
                value: "0x0",
            }],
        });

        setStatus("tx sent! hash: " + txHash.slice(0, 16) + "... submitting...");

        // Submit tx_hash to backend
        const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
        const res = await fetch("/api/payments/crypto/submit/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({
                chain: chainKey,
                tx_hash: txHash,
                website_url: websiteUrl,
            }),
        });

        const result = await res.json();
        if (result.error) {
            setStatus("payment sent but submission failed: " + result.error, true);
        } else {
            setStatus("payment submitted! tx: " + txHash.slice(0, 20) + "... we'll verify it shortly.");
            // Update UI
            const payBtn = document.getElementById("pay-crypto-btn");
            if (payBtn) {
                payBtn.disabled = true;
                payBtn.textContent = "[ payment submitted ]";
            }
        }
    } catch (err) {
        if (err.code === 4001) {
            setStatus("transaction rejected.", true);
        } else {
            setStatus("transaction failed: " + err.message, true);
        }
    }
}

async function payWithDodo() {
    const websiteUrl = document.getElementById("payment-website-url")?.value;
    if (!websiteUrl) {
        setStatus("missing website info.", true);
        return;
    }

    setStatus("creating checkout session...");

    const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
    try {
        const res = await fetch("/api/payments/dodo/create/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({ website_url: websiteUrl }),
        });

        const result = await res.json();
        if (result.error) {
            setStatus("checkout failed: " + result.error, true);
            return;
        }

        const checkoutUrl = result.data?.checkout_url || result.checkout_url;
        if (checkoutUrl) {
            setStatus("redirecting to payment...");
            window.location.href = checkoutUrl;
        } else {
            setStatus("no checkout URL returned. something went wrong.", true);
        }
    } catch (err) {
        setStatus("checkout request failed: " + err.message, true);
    }
}
