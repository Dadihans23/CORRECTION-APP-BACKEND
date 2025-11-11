  // Document Active
  const sections = document.querySelectorAll("section");
  const navLi = document.querySelectorAll(".doc-nav li");
  window.onscroll = () => {
      var current = "";

      sections.forEach((section) => {
          const sectionTop = section.offsetTop;
          if (scrollY >= sectionTop - 60) {
              current = section.getAttribute("id");
          }
      });

      navLi.forEach((li) => {
          li.classList.remove("active");
          if (li.classList.contains(current)) {
              li.classList.add("active");
          }
      });
  };

// Accordion - Seulement si le conteneur existe
const accordionContainer = document.querySelector('.accordion-container');
if (accordionContainer) {
    new Accordion('.accordion-container', {
        duration: 200,
    });
} else {
    console.log('No accordion container found, skipping accordion initialization');
}
// Swiper
var swiper = new Swiper(".client-side", {
    loop: true,
    slidesPerView: 'auto',
    spaceBetween: 30,
    delay: 3000,
    autoHeight: true,
    pagination: {
        el: ".swiper-pagination",
    },
});

// Tobii
const tobii = new Tobii()

