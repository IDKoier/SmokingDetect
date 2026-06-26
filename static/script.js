document.addEventListener("DOMContentLoaded", function () {
const timeToggle = document.getElementById("time-toggle");
const locationToggle = document.getElementById("location-toggle");

const timeOptions = document.getElementById("time-options");
const locationOptions = document.getElementById("location-options");

timeToggle.addEventListener("click", function (event) {
    timeOptions.classList.toggle("hidden-options");
    event.stopPropagation();
});

locationToggle.addEventListener("click", function (event) {
    locationOptions.classList.toggle("hidden-options");
    event.stopPropagation();
});



});
