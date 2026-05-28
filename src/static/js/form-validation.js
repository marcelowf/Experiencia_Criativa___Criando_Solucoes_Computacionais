/**
 * Validação de formulários — Triagem SXF
 *
 * Aplica-se a qualquer <form novalidate>.
 * Erros inline com Bootstrap .is-invalid + .invalid-feedback.
 * Recursos: required, e-mail, minlength, password strength,
 *           confirm password, CPF mod11, pattern.
 */
(function () {
  'use strict';

  // ---------- helpers ----------

  function getLabel(field) {
    if (field.id) {
      const lbl = document.querySelector('label[for="' + field.id + '"]');
      if (lbl) return lbl.textContent.replace(/\s*\*\s*$/, '').trim();
    }
    return field.getAttribute('data-label') || field.getAttribute('placeholder') || field.name || 'Campo';
  }

  function getFeedbackContainer(field) {
    if (field.classList.contains('custom-control-input')) {
      return field.closest('.custom-control') || field.parentElement;
    }
    const inputGroup = field.closest('.input-group');
    if (inputGroup) {
      return inputGroup.closest('.form-group') || inputGroup.parentElement || inputGroup;
    }
    const inputIcon = field.closest('.input-icon');
    if (inputIcon) return inputIcon.parentElement || inputIcon;
    return field.closest('.form-group') || field.parentElement;
  }

  function getOrCreateFeedback(container) {
    let fb = Array.from(container.children).find(el => el.classList.contains('invalid-feedback'));
    if (!fb) {
      fb = document.createElement('div');
      fb.className = 'invalid-feedback';
      container.appendChild(fb);
    }
    return fb;
  }

  function showError(field, message) {
    field.classList.add('is-invalid');
    const fb = getOrCreateFeedback(getFeedbackContainer(field));
    fb.textContent = message;
    fb.classList.add('d-block');
  }

  function clearError(field) {
    field.classList.remove('is-invalid');
    const container = getFeedbackContainer(field);
    const fb = Array.from(container.children).find(el => el.classList.contains('invalid-feedback'));
    if (fb) fb.classList.remove('d-block');
  }

  // ---------- CPF ----------

  function validarCPF(cpf) {
    const d = cpf.replace(/\D/g, '');
    if (d.length !== 11 || /^(.)\1{10}$/.test(d)) return false;
    let s = 0;
    for (let i = 0; i < 9; i++) s += +d[i] * (10 - i);
    let r = (s * 10) % 11; if (r >= 10) r = 0;
    if (r !== +d[9]) return false;
    s = 0;
    for (let i = 0; i < 10; i++) s += +d[i] * (11 - i);
    r = (s * 10) % 11; if (r >= 10) r = 0;
    return r === +d[10];
  }

  function aplicarMascaraCPF(input) {
    input.addEventListener('blur', function () {
      const d = (this.value || '').replace(/\D/g, '');
      if (d.length === 11)
        this.value = d.substr(0,3)+'.'+d.substr(3,3)+'.'+d.substr(6,3)+'-'+d.substr(9,2);
    });
  }

  // ---------- senha ----------

  function validarForcaSenha(v) {
    if (v.length < 8)           return 'A senha deve ter no mínimo 8 caracteres.';
    if (!/[A-Za-z]/.test(v))   return 'A senha deve conter ao menos uma letra.';
    if (!/\d/.test(v))         return 'A senha deve conter ao menos um número.';
    return null;
  }

  // ---------- campo individual ----------

  function validateField(field) {
    if (['hidden','submit','button','reset','image'].includes(field.type)) return true;
    if (field.name === 'csrf_token') return true;
    // campos em container oculto (exceto checkboxes)
    if (field.type !== 'checkbox' && !field.offsetParent) return true;

    const label = getLabel(field);
    const value = field.type === 'checkbox' ? null : (field.value || '').trim();
    const req   = field.hasAttribute('required');

    // obrigatório
    if (req) {
      if (field.type === 'checkbox' && !field.checked) {
        showError(field, 'É obrigatório confirmar este campo.');
        return false;
      }
      if (field.type !== 'checkbox' && !value) {
        showError(field, field.tagName === 'SELECT'
          ? 'Selecione uma opção para ' + label + '.'
          : 'O campo ' + label + ' é obrigatório.');
        return false;
      }
    }

    if (!value) { clearError(field); return true; }

    // e-mail
    if (field.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      showError(field, 'Informe um e-mail válido.');
      return false;
    }

    // força da senha
    if ('passwordStrength' in field.dataset) {
      const err = validarForcaSenha(value);
      if (err) { showError(field, err); return false; }
    } else {
      const min = parseInt(field.getAttribute('minlength'));
      if (min && value.length < min) {
        showError(field, 'O campo ' + label + ' deve ter no mínimo ' + min + ' caracteres.');
        return false;
      }
    }

    // confirmar senha
    if (field.dataset.confirm) {
      const outro = document.querySelector(field.dataset.confirm);
      if (outro && value !== outro.value) {
        showError(field, 'As senhas não conferem.');
        return false;
      }
    }

    // CPF
    if ('cpf' in field.dataset || field.name === 'cpf' || field.name === 'resp_cpf') {
      const digits = value.replace(/\D/g, '');
      if (digits.length > 0 && !validarCPF(digits)) {
        showError(field, 'CPF inválido. Verifique os dígitos.');
        return false;
      }
    }

    // pattern
    if (field.hasAttribute('pattern') && value) {
      const patt = new RegExp('^(?:' + field.getAttribute('pattern') + ')$');
      if (!patt.test(value)) {
        showError(field, field.getAttribute('title') || 'Formato inválido para ' + label + '.');
        return false;
      }
    }

    clearError(field);
    return true;
  }

  // ---------- formulário completo ----------

  function validateForm(form) {
    let ok = true;
    form.querySelectorAll('input, select, textarea').forEach(function (f) {
      if (!validateField(f)) ok = false;
    });
    return ok;
  }

  // ---------- inicialização ----------

  document.addEventListener('DOMContentLoaded', function () {

    // máscara de CPF em todos os campos de CPF da página
    document.querySelectorAll('[name="cpf"], [name="resp_cpf"]').forEach(aplicarMascaraCPF);

    document.querySelectorAll('form[novalidate]').forEach(function (form) {

      form.addEventListener('submit', function (e) {
        if (!validateForm(form)) {
          e.preventDefault();
          e.stopPropagation();
          const first = form.querySelector('.is-invalid');
          if (first) {
            first.scrollIntoView({ behavior: 'smooth', block: 'center' });
            first.focus();
          }
        }
      });

      form.querySelectorAll('input, select, textarea').forEach(function (f) {
        // validar ao sair do campo (exceto campo de confirmação — só no submit)
        f.addEventListener('blur', function () {
          if (!f.dataset.confirm) validateField(f);
        });
        // limpar erro ao corrigir
        f.addEventListener('input', function () { clearError(f); });
        f.addEventListener('change', function () {
          clearError(f);
          if (f.type === 'checkbox') validateField(f);
        });
      });
    });
  });
})();
