// noinspection JSUnresolvedVariable
(function(arguments, window) {

  const done = arguments[0];

  // basically just a simple wrapper around XMLHttpRequest
  async function get_url(url) {
    return new Promise(function (resolve, reject) {
      const xhttp = new XMLHttpRequest();

      xhttp.onload = function () {
        if (this.status >= 200 && this.status < 300) {
          resolve(xhttp.responseText);
        } else {
          reject({
            status: this.status,
            statusText: xhttp.statusText
          });
        }
      };

      xhttp.onerror = function () {
        reject({
          status: this.status,
          statusText: xhttp.statusText
        });
      };

      xhttp.open("GET", url, true);
      xhttp.setRequestHeader("Authorization", "Basic OlZDR00tRjg3Wi1RN1Za");
      xhttp.send();
    });
  }

  async function process() {
    // path being something like
    // /terminservice/suche/VCGM-F87Z-Q7VZ/75175/L920
    let code, postal_code, vaccine_code;

    [,,,code,postal_code,vaccine_code] = window.location.pathname.split('/');

    return await get_url(`/rest/suche/ersttermin?allOf=&someOf=${vaccine_code}&plz=${postal_code}&daytime=11111111111111&radius=10`);
  }

  process().then(
      result => done(result),
      error => done(error)
  );

})(arguments, window);
