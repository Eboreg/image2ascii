window.onload = () => {
    var form = document.querySelector("#form");
    var isSubmitting = false;


    /** UTILITY FUNCTIONS ****************************************************/

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

    function formdataToObject() {
        var obj = {};
        [
            "uuid", "flag", "color", "crop", "invert", "negative", "fill-all",
            "full-rgb", "contrast", "brightness", "color-balance"
        ].forEach(fieldname => {
            var field = document.getElementById(fieldname);
            if (field.type == "checkbox") obj[fieldname] = field.checked;
            else obj[fieldname] = field.value;
        });
        return obj;
    }

    function submitForm(filename, pushState=true) {
        if (!isSubmitting) {
            isSubmitting = true;
            document.querySelector("#submit").disabled = true;
            var toastText = "Updating ...";
            if (filename) toastText = "Processing " + filename + " ...";
            var toast = showToast("bg-primary", toastText, false);
            var formdata = new FormData(form);
            var req = new XMLHttpRequest();
            req.onload = () => {
                var response = JSON.parse(req.response);
                if (response.error) {
                    showToast("bg-danger", response.error);
                } else {
                    document.querySelector("#uuid").value = response.uuid;
                    if (response.output != null) {
                        document.querySelector("#output").innerHTML = response.output;
                        document.querySelector("#result-box").classList.remove("d-none");
                    }
                    else {
                        document.querySelector("#result-box").classList.add("d-none");
                    }
                    var url = new URL(window.location);
                    if (typeof response.uuid == "undefined" || response.uuid == null) {
                        url.searchParams.delete("uuid");
                    }
                    else {
                        url.searchParams.set("uuid", response.uuid);
                    }
                    if (window.location != url.href) {
                        if (pushState) {
                            window.history.pushState(formdataToObject(), "", url);
                        }
                        else {
                            window.history.replaceState(formdataToObject(), "", url);
                        }
                    }
                }
                document.querySelector("#submit").disabled = false;
                // Unset image & image-url to avoid unnecessary future fetches
                document.querySelector("#image-url").value = "";
                document.querySelector("#image").value = "";
                isSubmitting = false;
                toast.hide();
            };
            req.open("post", form.action);
            req.send(formdata);
        } else {
            showToast("bg-secondary", "I'm busy processing another image. Don't get your knickers in a twist!");
        }
    }


    /** BROWSER STATE ********************************************************/

    window.addEventListener("popstate", event => {
        if (event && event.state && Object.keys(event.state).length > 0) {
            [
                "uuid", "flag", "color", "crop", "invert", "negative", "fill-all",
                "full-rgb", "contrast", "brightness", "color-balance"
            ].forEach(fieldname => {
                var field = document.getElementById(fieldname);
                if (field.type == "checkbox") {
                    field.checked = event.state[fieldname];
                } else {
                    field.value = event.state[fieldname];
                }
                field.dispatchEvent(new Event("input"));
            });
            submitForm(null, false);
        }
    });


    /** FORM EVENT LISTENERS *************************************************/

    document.querySelector("#color").addEventListener("input", event => {
        // If not color, then fill-all and full-rgb make no sense
        document.querySelector("#fill-all").disabled = !event.target.checked;
        document.querySelector("#full-rgb").disabled = !event.target.checked;
    });

    function onRangeChanged(elem, value) {
        // Updates legend at the side of range input
        document.querySelector("#" + elem.id + "-value").textContent = Number(value).toPrecision(2);
    }

    document.querySelectorAll("input[type=range]").forEach(elem => {
        // Update range legends on user input
        elem.addEventListener("input", event => {
            onRangeChanged(elem, event.target.value);
        })
    });

    document.querySelector("#image").addEventListener("input", event => {
        // When image is selected, unset flag & image-url field and submit
        if (event.target.value) {
            document.querySelector("#flag").value = "";
            document.querySelector("#image-url").value = "";
            var arr = event.target.value.split("\\");
            submitForm(arr[arr.length - 1]);
        }
    });

    document.querySelector("#image-url").addEventListener("input", event => {
        // When image-url is set, unset flag & image field and submit
        if (event.target.value) {
            document.querySelector("#flag").value = "";
            document.querySelector("#image").value = "";
            var arr = event.target.value.split("/");
            submitForm(arr[arr.length - 1]);
        }
    });

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

    form.addEventListener("submit", event => {
        event.preventDefault();
        submitForm();
    });


    /** DRAG & DROP **********************************************************/

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


    /** PASTING **************************************************************/

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
