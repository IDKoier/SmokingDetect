document.addEventListener("DOMContentLoaded", function () {
// 获取按钮元素
const timeToggle = document.getElementById("time-toggle");
const locationToggle = document.getElementById("location-toggle");

// 获取对应的选项
const timeOptions = document.getElementById("time-options");
const locationOptions = document.getElementById("location-options");

// 为按钮添加点击事件处理程序
timeToggle.addEventListener("click", function (event) {
    timeOptions.classList.toggle("hidden-options");
    event.stopPropagation();
});

locationToggle.addEventListener("click", function (event) {
    locationOptions.classList.toggle("hidden-options");
    event.stopPropagation();
});



});
