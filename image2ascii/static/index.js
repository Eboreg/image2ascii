window.onload = () => {
    var form = document.querySelector("#form");
    var isSubmitting = false;

    function showToast(bgClass, text, autohide=true) {
        // bgClass = e.g. "bg-primary", "bg-danger"
        // text will be shortened to max 200 chars (+ ellipsis)
        if (text.length > 200)
            text = text.slice(0, 200) + " ...";
        var toastElem = document.querySelector("#toast-template>.toast").cloneNode(true);
        toastElem.classList.add(bgClass);
        toastElem.querySelector(".toast-body").textContent = text;
        document.querySelector("#toast-container").append(toastElem);
        var toast = new bootstrap.Toast(toastElem, {autohide: autohide});
        toast.show();
        return toast;
    }

    function onRangeChanged(elem, value) {
        // Updates legend at the side of range input
        document.querySelector("#" + elem.id + "-value").textContent = Number(value).toPrecision(2);
    }

    function submitForm(filename) {
        if (!isSubmitting) {
            isSubmitting = true;
            document.querySelector("#submit").disabled = true;
            var toastText = "Updating ...";
            if (filename) toastText = "Processing " + filename + " ...";
            var toast = showToast("bg-primary", toastText, false);
            var req = new XMLHttpRequest();
            req.onload = () => {
                var response = JSON.parse(req.response);
                if (response.error) {
                    showToast("bg-danger", response.error);
                } else {
                    document.querySelector("#output").innerHTML = response.output;
                    document.querySelector("#result-box").style.display = "block";
                }
                document.querySelector("#submit").disabled = false;
                isSubmitting = false;
                toast.hide();
            };
            req.open("post", form.action);
            req.send(new FormData(form));
        } else {
            showToast("bg-secondary", "I'm busy processing another image. Don't get your knickers in a twist!");
        }
    }

    document.querySelector("#color").addEventListener("input", event => {
        // If not color, then fill-all and full-rgb make no sense
        document.querySelector("#fill-all").disabled = !event.target.checked;
        document.querySelector("#full-rgb").disabled = !event.target.checked;
    })

    document.querySelectorAll("input[type=range]").forEach(elem => {
        // Update range legends on user input
        elem.addEventListener("input", event => {
            onRangeChanged(elem, event.target.value);
        })
    })

    document.querySelector("#image").addEventListener("input", event => {
        // When image is selected, unset flag & image-url field and submit
        if (event.target.value) {
            document.querySelector("#flag").value = "";
            document.querySelector("#image-url").value = "";
            var arr = event.target.value.split("\\");
            submitForm(arr[arr.length - 1]);
        }
    })

    document.querySelector("#image-url").addEventListener("input", event => {
        // When image-url is set, unset flag & image field and submit
        if (event.target.value) {
            document.querySelector("#flag").value = "";
            document.querySelector("#image").value = "";
            var arr = event.target.value.split("/");
            submitForm(arr[arr.length - 1]);
        }
    })

    document.querySelector("#flag").addEventListener("input", event => {
        // When flag is selected, set some sensible default values,
        // unset image & image-url field, and submit
        if (event.target.value) {
            ["#color", "#fill-all", "#full-rgb"].forEach(id => {
                document.querySelector(id).checked = true;
            });
            ["#invert", "#negative", "#crop"].forEach(id => {
                document.querySelector(id).checked = false;
            })
            document.querySelector("#image").value = "";
            document.querySelector("#image-url").value = "";
            submitForm(event.target.value);
        }
    });

    document.querySelector("button#reset").addEventListener("click", () => {
        // "Reset adjustments" button; revert to defaults
        ["#color", "#crop", "#full-rgb"].forEach(id => {
            document.querySelector(id).checked = true;
        });

        ["#invert", "#negative", "#fill-all"].forEach(id => {
            document.querySelector(id).checked = false;
        });

        document.querySelectorAll("input[type=range]").forEach(elem => {
            elem.value = 1.0;
            onRangeChanged(elem, 1.0);
        });
    });

    var dropOverlay = document.querySelector(".drop-overlay");

    document.body.addEventListener("dragenter", event => {
        // When dragging file over document, show overlay
        event.preventDefault();
        event.stopPropagation();
        dropOverlay.style.display = "block";
    });
    document.body.addEventListener("drop", event => {
        event.preventDefault();
    });
    dropOverlay.addEventListener("dragover", event => {
        event.preventDefault();
        event.stopPropagation();
    });
    dropOverlay.addEventListener("dragleave", event => {
        // Drag leaving the overlay; back to normal
        event.preventDefault();
        event.stopPropagation();
        dropOverlay.style.display = "none";
    });
    dropOverlay.addEventListener("drop", event => {
        // File dropped; hide overlay and trigger "input" event on image
        // field, which in turn triggers a form submit (above)
        event.preventDefault();
        event.stopPropagation();
        dropOverlay.style.display = "none";
        if (event.dataTransfer) {
            if (event.dataTransfer.files.length > 0) {
                document.querySelector("#image").files = event.dataTransfer.files;
                document.querySelector("#image").dispatchEvent(new Event("input"));
            }
            else if (event.dataTransfer.getData("text")) {
                var url = event.dataTransfer.getData("text");
                if (url) {
                    document.querySelector("#image-url").value = url;
                    document.querySelector("#image-url").dispatchEvent(new Event("input"));
                }
            }
        }
    });

    form.addEventListener("submit", event => {
        event.preventDefault();
        submitForm();
    });

    document.addEventListener("paste", async event => {
        // Handle pasted images
        event.preventDefault();
        event.stopPropagation();
        if (event.clipboardData) {
            if (event.clipboardData.files.length > 0) {
                document.querySelector("#image").files = event.clipboardData.files;
                document.querySelector("#image").dispatchEvent(new Event("input"));
            }
        }
    });
};
