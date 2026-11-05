(() => {
    "use strict";

    const BASE_URL = "/api/v1/image-to-code";

    const $ = (id) => document.getElementById(id);

    let selectedImage = null;
    let currentMode = "upload";

    function getHeaders() {
        const tenantId = $("tenantSelect")?.value;

        if (!tenantId) {
            throw new Error("Please select an organization first.");
        }

        return {
            "X-Tenant-ID": tenantId
        };
    }

    function getGeminiKey() {
        const key = $("i2cGeminiKey").value.trim();

        if (!key) {
            throw new Error("Please enter your Gemini API key.");
        }

        return key;
    }

    function setStatus(message, isError = false) {
        const status = $("i2cStatus");
        status.textContent = message;
        status.style.color = isError ? "#dc2626" : "";
    }

    function setLoading(buttonId, loading, loadingText, normalText) {
        const button = $(buttonId);
        button.disabled = loading;
        button.textContent = loading ? loadingText : normalText;
    }

    async function sendRequest(url, options) {
        const response = await fetch(BASE_URL + url, options);

        let result;

        try {
            result = await response.json();
        } catch {
            throw new Error("The server returned an invalid response.");
        }

        if (!response.ok) {
            throw new Error(
                result.detail || `Request failed (${response.status}).`
            );
        }

        return result;
    }

    function displayResult(code) {
        $("i2cCode").value = code;
        $("i2cResult").classList.remove("hidden");

        updatePreview();

        $("i2cResult").scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }

    function updatePreview() {
        const code = $("i2cCode").value;

        // The preview is isolated in a sandboxed iframe.
        $("i2cPreview").srcdoc = code;
    }

    // Switch between the two generation modes.
    document.querySelectorAll(".i2c-mode").forEach(button => {
        button.addEventListener("click", () => {
            currentMode = button.dataset.mode;

            document.querySelectorAll(".i2c-mode").forEach(item => {
                item.classList.toggle("active", item === button);
            });

            $("i2cUploadMode").classList.toggle(
                "hidden",
                currentMode !== "upload"
            );

            $("i2cTextMode").classList.toggle(
                "hidden",
                currentMode !== "text"
            );

            setStatus("Ready to generate.");
        });
    });

    // Select and preview an uploaded image.
    $("i2cImageInput").addEventListener("change", event => {
        const file = event.target.files[0];

        if (!file) return;

        const allowed = [
            "image/png",
            "image/jpeg",
            "image/webp"
        ];

        if (!allowed.includes(file.type)) {
            setStatus("Please select a PNG, JPG or WEBP image.", true);
            event.target.value = "";
            selectedImage = null;
            return;
        }

        if (file.size > 20 * 1024 * 1024) {
            setStatus("Image size must not exceed 20 MB.", true);
            event.target.value = "";
            selectedImage = null;
            return;
        }

        selectedImage = file;

        const preview = $("i2cUploadedImage");
        preview.src = URL.createObjectURL(file);
        preview.classList.remove("hidden");

        $("i2cImageBox").querySelector("span").textContent = file.name;

        setStatus("Image selected successfully.");
    });

    // Image to code.
    $("i2cGenerateUpload").addEventListener("click", async () => {
        if (!selectedImage) {
            setStatus("Please select an image first.", true);
            return;
        }

        try {
            const geminiKey = getGeminiKey();
            const headers = getHeaders();

            const formData = new FormData();
            formData.append("image", selectedImage);
            formData.append("gemini_api_key", geminiKey);
            formData.append("output_type", "HTML");

            setLoading(
                "i2cGenerateUpload",
                true,
                "Generating code...",
                "Generate Code"
            );

            setStatus("Gemini is analysing your image...");

            const result = await sendRequest("/from-image", {
                method: "POST",
                headers,
                body: formData
            });

            displayResult(result.code);
            setStatus("Code generated successfully.");

        } catch (error) {
            setStatus(error.message, true);
        } finally {
            setLoading(
                "i2cGenerateUpload",
                false,
                "Generating code...",
                "Generate Code"
            );
        }
    });

    // Text to image and code.
    $("i2cGenerateText").addEventListener("click", async () => {
        try {
            const prompt = $("i2cPrompt").value.trim();
            const geminiKey = getGeminiKey();
            const pollinationsKey = $("i2cPollinationsKey").value.trim();

            if (!prompt) {
                throw new Error("Please describe the image you want to generate.");
            }

            if (!pollinationsKey) {
                throw new Error("Please enter your Pollinations API key.");
            }

            setLoading(
                "i2cGenerateText",
                true,
                "Generating image and code...",
                "Generate Image and Code"
            );

            setStatus("Generating image with Pollinations...");

            const result = await sendRequest("/from-text", {
                method: "POST",
                headers: {
                    ...getHeaders(),
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    prompt,
                    gemini_api_key: geminiKey,
                    pollinations_api_key: pollinationsKey,
                    output_type: "HTML"
                })
            });

            $("i2cGeneratedImage").src = result.image;
            $("i2cGeneratedImage").classList.remove("hidden");

            displayResult(result.code);
            setStatus("Image and code generated successfully.");

        } catch (error) {
            setStatus(error.message, true);
        } finally {
            setLoading(
                "i2cGenerateText",
                false,
                "Generating image and code...",
                "Generate Image and Code"
            );
        }
    });

    // Improve generated code.
    $("i2cImprove").addEventListener("click", async () => {
        try {
            const instruction = $("i2cImprovePrompt").value.trim();
            const code = $("i2cCode").value.trim();

            if (!code) {
                throw new Error("Generate or enter code first.");
            }

            if (!instruction) {
                throw new Error("Please enter an improvement instruction.");
            }

            setLoading(
                "i2cImprove",
                true,
                "Improving...",
                "Improve Code"
            );

            setStatus("Gemini is improving your code...");

            const result = await sendRequest("/improve", {
                method: "POST",
                headers: {
                    ...getHeaders(),
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    code,
                    instruction,
                    gemini_api_key: getGeminiKey(),
                    output_type: "HTML"
                })
            });

            displayResult(result.code);
            $("i2cImprovePrompt").value = "";

            setStatus("Code improved successfully.");

        } catch (error) {
            setStatus(error.message, true);
        } finally {
            setLoading(
                "i2cImprove",
                false,
                "Improving...",
                "Improve Code"
            );
        }
    });

    // Copy code.
    $("i2cCopy").addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText($("i2cCode").value);
            setStatus("Code copied successfully.");
        } catch {
            setStatus("Unable to copy code. Check browser permissions.", true);
        }
    });

    // Download code.
    $("i2cDownload").addEventListener("click", () => {
        const code = $("i2cCode").value;

        if (!code.trim()) {
            setStatus("There is no code to download.", true);
            return;
        }

        const blob = new Blob([code], {
            type: "text/html;charset=utf-8"
        });

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = "generated-design.html";
        link.click();

        URL.revokeObjectURL(url);
        setStatus("HTML file downloaded.");
    });

    // Refresh preview when the code is edited.
    $("i2cCode").addEventListener("input", updatePreview);

})();